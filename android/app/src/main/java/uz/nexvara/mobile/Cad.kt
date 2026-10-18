package uz.nexvara.mobile

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.round
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * «Chizma» on the phone: a small CAD model in millimetres (Y up, like DXF), a recogniser that
 * turns finger strokes into clean geometry, and the JSON the PC editor uses (app/api_cad.py),
 * so a phone drawing is saved on the PC as a real AutoCAD DXF.
 */
data class Pt(val x: Double, val y: Double) {
    operator fun plus(o: Pt) = Pt(x + o.x, y + o.y)
    operator fun minus(o: Pt) = Pt(x - o.x, y - o.y)
    operator fun times(k: Double) = Pt(x * k, y * k)
    fun dist(o: Pt) = hypot(x - o.x, y - o.y)
}

sealed class CadE {
    data class Line(val a: Pt, val b: Pt) : CadE()
    data class Poly(val pts: List<Pt>, val closed: Boolean) : CadE()
    data class Circle(val c: Pt, val r: Double) : CadE()
    /** Counter-clockwise from [start] to [end], degrees (as in DXF). */
    data class Arc(val c: Pt, val r: Double, val start: Double, val end: Double) : CadE()
    data class Text(val p: Pt, val text: String, val h: Double) : CadE()
    /** Linear dimension: measured along [rot] degrees (0 = horizontal), line through [base]. */
    data class Dim(val a: Pt, val b: Pt, val base: Pt, val rot: Double) : CadE()
}

private fun deg(rad: Double) = ((Math.toDegrees(rad) % 360) + 360) % 360

object CadGeom {
    fun length(e: CadE): Double = when (e) {
        is CadE.Line -> e.a.dist(e.b)
        is CadE.Poly -> e.pts.zipWithNext().sumOf { (a, b) -> a.dist(b) } + if (e.closed && e.pts.size > 2) e.pts.last().dist(e.pts.first()) else 0.0
        is CadE.Circle -> 2 * Math.PI * e.r
        is CadE.Arc -> Math.toRadians(sweep(e.start, e.end)) * e.r
        else -> 0.0
    }

    fun sweep(start: Double, end: Double): Double { val s = ((end - start) % 360 + 360) % 360; return if (s == 0.0) 360.0 else s }

    fun dimValue(d: CadE.Dim): Double {
        val r = Math.toRadians(d.rot); val u = Pt(cos(r), sin(r))
        return abs((d.b.x - d.a.x) * u.x + (d.b.y - d.a.y) * u.y)
    }

    /** End points to snap to. */
    fun ends(e: CadE): List<Pt> = when (e) {
        is CadE.Line -> listOf(e.a, e.b, (e.a + e.b) * 0.5)
        is CadE.Poly -> e.pts
        is CadE.Circle -> listOf(e.c) + (0 until 4).map { e.c + Pt(cos(it * Math.PI / 2), sin(it * Math.PI / 2)) * e.r }
        is CadE.Arc -> listOf(e.c, at(e, e.start), at(e, e.end))
        is CadE.Text -> listOf(e.p)
        is CadE.Dim -> listOf(e.a, e.b)
    }

    fun at(a: CadE.Arc, d: Double) = a.c + Pt(cos(Math.toRadians(d)), sin(Math.toRadians(d))) * a.r

    private fun segDist(p: Pt, a: Pt, b: Pt): Double {
        val dx = b.x - a.x; val dy = b.y - a.y; val l = dx * dx + dy * dy
        val t = if (l == 0.0) 0.0 else ((p.x - a.x) * dx + (p.y - a.y) * dy) / l
        val k = t.coerceIn(0.0, 1.0)
        return p.dist(Pt(a.x + dx * k, a.y + dy * k))
    }

    fun distance(e: CadE, p: Pt): Double = when (e) {
        is CadE.Line -> segDist(p, e.a, e.b)
        is CadE.Poly -> (e.pts.zipWithNext() + if (e.closed && e.pts.size > 2) listOf(e.pts.last() to e.pts.first()) else emptyList())
            .minOfOrNull { (a, b) -> segDist(p, a, b) } ?: Double.MAX_VALUE
        is CadE.Circle -> abs(p.dist(e.c) - e.r)
        is CadE.Arc -> {
            val a = deg(atan2(p.y - e.c.y, p.x - e.c.x))
            if (((a - e.start) % 360 + 360) % 360 <= sweep(e.start, e.end)) abs(p.dist(e.c) - e.r)
            else min(p.dist(at(e, e.start)), p.dist(at(e, e.end)))
        }
        is CadE.Text -> {
            val w = e.text.length * e.h * 0.62
            if (p.x in e.p.x..(e.p.x + w) && p.y in e.p.y..(e.p.y + e.h)) 0.0 else p.dist(e.p)
        }
        is CadE.Dim -> min(segDist(p, e.a, e.b), p.dist(e.base))
    }

    /** Ramer–Douglas–Peucker: the corners of a hand-drawn stroke. */
    fun simplify(pts: List<Pt>, eps: Double): List<Pt> {
        if (pts.size < 3) return pts
        var idx = 0; var best = 0.0
        for (i in 1 until pts.size - 1) {
            val d = segDist(pts[i], pts.first(), pts.last())
            if (d > best) { best = d; idx = i }
        }
        if (best <= eps) return listOf(pts.first(), pts.last())
        val left = simplify(pts.subList(0, idx + 1), eps)
        val right = simplify(pts.subList(idx, pts.size), eps)
        return left.dropLast(1) + right
    }

    /** Circle through three points, or null when they are on one line. */
    fun circle3(a: Pt, b: Pt, c: Pt): Pair<Pt, Double>? {
        val d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
        if (abs(d) < 1e-9) return null
        val ux = ((a.x * a.x + a.y * a.y) * (b.y - c.y) + (b.x * b.x + b.y * b.y) * (c.y - a.y) + (c.x * c.x + c.y * c.y) * (a.y - b.y)) / d
        val uy = ((a.x * a.x + a.y * a.y) * (c.x - b.x) + (b.x * b.x + b.y * b.y) * (a.x - c.x) + (c.x * c.x + c.y * c.y) * (b.x - a.x)) / d
        val center = Pt(ux, uy)
        return center to center.dist(a)
    }

    fun round1(v: Double) = round(v * 10) / 10
}

/** Finger stroke → clean geometry. [tol] is the finger's precision in millimetres. */
object Recognizer {
    fun snapAngle(a: Pt, b: Pt, stepDeg: Double = 15.0, within: Double = 6.0): Pt {
        val ang = Math.toDegrees(atan2(b.y - a.y, b.x - a.x))
        val target = round(ang / stepDeg) * stepDeg
        if (abs(ang - target) > within) return b
        val len = a.dist(b); val r = Math.toRadians(target)
        return Pt(a.x + len * cos(r), a.y + len * sin(r))
    }

    fun recognize(stroke: List<Pt>, tol: Double, tidy: Boolean): CadE? {
        if (stroke.size < 2) return null
        val total = stroke.zipWithNext().sumOf { (a, b) -> a.dist(b) }
        if (total < tol * 2) return null
        val first = stroke.first(); val last = stroke.last()
        val xs = stroke.map { it.x }; val ys = stroke.map { it.y }
        val diag = hypot(xs.max() - xs.min(), ys.max() - ys.min())
        val closed = first.dist(last) < max(0.15 * total, 2 * tol) && total > 6 * tol
        if (closed) {
            val c = Pt(xs.average(), ys.average())
            val radii = stroke.map { it.dist(c) }
            val mean = radii.average()
            val sd = sqrt(radii.map { (it - mean) * (it - mean) }.average())
            if (mean > 0 && sd / mean < 0.13) return CadE.Circle(c, CadGeom.round1(mean))
            var poly = CadGeom.simplify(stroke, max(tol, 0.06 * diag)).toMutableList()
            if (poly.size > 2 && poly.first().dist(poly.last()) < max(0.2 * diag, 2 * tol)) poly.removeAt(poly.lastIndex)
            if (poly.size == 4 && tidy && isRectangular(poly)) {
                val axis = abs(Math.toDegrees(atan2(poly[1].y - poly[0].y, poly[1].x - poly[0].x))) % 90
                if (axis < 12 || axis > 78) {  // nearly level: an exact, axis-aligned rectangle
                    val x1 = poly.minOf { it.x }; val x2 = poly.maxOf { it.x }
                    val y1 = poly.minOf { it.y }; val y2 = poly.maxOf { it.y }
                    return CadE.Poly(listOf(Pt(x1, y1), Pt(x2, y1), Pt(x2, y2), Pt(x1, y2)), true)
                }
            }
            if (poly.size >= 3) return CadE.Poly(poly, true)
        }
        // open: a straight line, an arc or a polyline
        val chord = first.dist(last)
        val dev = stroke.maxOf { p -> distToLine(p, first, last) }
        if (chord > 0 && dev < max(0.06 * chord, tol * 0.8)) {
            return CadE.Line(first, if (tidy) snapAngle(first, last) else last)
        }
        val mid = stroke[stroke.size / 2]
        CadGeom.circle3(first, mid, last)?.let { (c, r) ->
            val err = stroke.maxOf { abs(it.dist(c) - r) }
            if (err < max(0.08 * r, tol) && r < 50 * diag) {
                val a0 = deg(atan2(first.y - c.y, first.x - c.x)); val a1 = deg(atan2(last.y - c.y, last.x - c.x))
                val ccw = cross(first - c, mid - c) > 0
                return if (ccw) CadE.Arc(c, CadGeom.round1(r), a0, a1) else CadE.Arc(c, CadGeom.round1(r), a1, a0)
            }
        }
        val poly = CadGeom.simplify(stroke, max(tol, 0.04 * diag))
        val straight = if (tidy) poly.mapIndexed { i, p -> if (i == 0) p else snapAngle(poly[i - 1], p) } else poly
        return if (straight.size == 2) CadE.Line(straight[0], straight[1]) else CadE.Poly(straight, false)
    }

    private fun cross(a: Pt, b: Pt) = a.x * b.y - a.y * b.x

    private fun distToLine(p: Pt, a: Pt, b: Pt): Double {
        val l = a.dist(b); if (l == 0.0) return p.dist(a)
        return abs((b.x - a.x) * (a.y - p.y) - (a.x - p.x) * (b.y - a.y)) / l
    }

    private fun isRectangular(p: List<Pt>): Boolean = (0 until 4).all { i ->
        val a = p[(i + 3) % 4] - p[i]; val b = p[(i + 1) % 4] - p[i]
        val cosA = (a.x * b.x + a.y * b.y) / (hypot(a.x, a.y) * hypot(b.x, b.y))
        abs(cosA) < 0.26  // within ~15° of a right angle
    }
}

/** The drawing being edited on the phone (+ entities the phone does not edit, kept as they are). */
class CadState {
    val items = mutableStateListOf<CadE>()
    var extra: List<JSONObject> = emptyList()
    var name by mutableStateOf("Telefon chizmasi")
    var path by mutableStateOf<String?>(null)
    var drawings by mutableStateOf<List<Pair<String, String>>>(emptyList())  // name, path on the PC
    var lastSaved by mutableStateOf<JSONObject?>(null)
    val undo = ArrayDeque<List<CadE>>()
    val redo = ArrayDeque<List<CadE>>()

    fun snapshot() { undo.addLast(items.toList()); if (undo.size > 80) undo.removeFirst(); redo.clear() }
    fun add(e: CadE) { snapshot(); items.add(e) }
    fun replace(i: Int, e: CadE) { snapshot(); items[i] = e }
    fun remove(i: Int) { snapshot(); items.removeAt(i) }
    fun undo() { undo.removeLastOrNull()?.let { redo.addLast(items.toList()); items.clear(); items.addAll(it) } }
    fun redo() { redo.removeLastOrNull()?.let { undo.addLast(items.toList()); items.clear(); items.addAll(it) } }
    fun clear() { snapshot(); items.clear(); extra = emptyList(); path = null }

    fun toJson(): JSONObject {
        val ents = JSONArray()
        fun o(type: String) = JSONObject().put("type", type).put("layer", "0")
        items.forEach { e ->
            ents.put(when (e) {
                is CadE.Line -> o("line").put("x1", e.a.x).put("y1", e.a.y).put("x2", e.b.x).put("y2", e.b.y)
                is CadE.Poly -> o("polyline").put("closed", e.closed)
                    .put("points", JSONArray(e.pts.map { JSONArray(listOf(it.x, it.y, 0.0)) }))
                is CadE.Circle -> o("circle").put("cx", e.c.x).put("cy", e.c.y).put("r", e.r)
                is CadE.Arc -> o("arc").put("cx", e.c.x).put("cy", e.c.y).put("r", e.r).put("start", e.start).put("end", e.end)
                is CadE.Text -> o("text").put("x", e.p.x).put("y", e.p.y).put("text", e.text).put("h", e.h).put("rot", 0)
                is CadE.Dim -> o("ldim").put("x1", e.a.x).put("y1", e.a.y).put("x2", e.b.x).put("y2", e.b.y)
                    .put("bx", e.base.x).put("by", e.base.y).put("rot", e.rot).put("label", "")
            })
        }
        extra.forEach { ents.put(it) }
        return JSONObject().put("units", "mm").put("entities", ents)
            .put("layers", JSONArray().put(JSONObject().put("name", "0").put("color", 7).put("lineweight", 35).put("visible", true)))
    }

    fun load(drawing: JSONObject) {
        val got = mutableListOf<CadE>(); val keep = mutableListOf<JSONObject>()
        val arr = drawing.optJSONArray("entities") ?: JSONArray()
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            fun d(k: String) = o.optDouble(k, 0.0)
            when (o.optString("type")) {
                "line" -> got += CadE.Line(Pt(d("x1"), d("y1")), Pt(d("x2"), d("y2")))
                "polyline" -> {
                    val pts = o.optJSONArray("points") ?: JSONArray()
                    val bulged = (0 until pts.length()).any { (pts.optJSONArray(it)?.optDouble(2, 0.0) ?: 0.0) != 0.0 }
                    if (bulged) keep += o  // rounded corners stay exactly as drawn on the PC
                    else got += CadE.Poly((0 until pts.length()).mapNotNull { k -> pts.optJSONArray(k)?.let { Pt(it.optDouble(0), it.optDouble(1)) } },
                        o.optBoolean("closed"))
                }
                "circle" -> got += CadE.Circle(Pt(d("cx"), d("cy")), d("r"))
                "arc" -> got += CadE.Arc(Pt(d("cx"), d("cy")), d("r"), d("start"), d("end"))
                "text" -> got += CadE.Text(Pt(d("x"), d("y")), o.optString("text"), o.optDouble("h", 3.5))
                "ldim" -> got += CadE.Dim(Pt(d("x1"), d("y1")), Pt(d("x2"), d("y2")), Pt(d("bx"), d("by")), d("rot"))
                else -> keep += o
            }
        }
        undo.clear(); redo.clear(); items.clear(); items.addAll(got); extra = keep
    }
}

private fun enc(s: String) = java.net.URLEncoder.encode(s, "UTF-8")

// ---------------- talking to the PC ----------------
fun AppModel.cadList() = call(quiet = true, block = get("/api/v1/cad")) {
    val arr = it.optJSONArray("drawings") ?: JSONArray()
    cad.drawings = (0 until arr.length()).mapNotNull { k -> arr.optJSONObject(k)?.let { o -> o.optString("name") to o.optString("path") } }
}

fun AppModel.cadLoad(path: String) = call(block = get("/api/v1/cad/drawing?path=${enc(path)}")) {
    cad.load(it.optJSONObject("drawing") ?: JSONObject())
    cad.path = it.optString("path"); cad.name = it.optString("name").removeSuffix(".dxf")
    notice = if (it.optBoolean("truncated")) "Chizma katta: telefonda bir qismi ko‘rsatildi" else "«${cad.name}» ochildi"
}

fun AppModel.cadSave(openOnPc: Boolean) {
    if (cad.items.isEmpty() && cad.extra.isEmpty()) { notice = "Chizma bo‘sh"; return }
    val body = JSONObject().put("name", cad.name).put("drawing", cad.toJson()).put("open_on_pc", openOnPc)
    call(block = post("/api/v1/cad", body)) {
        cad.lastSaved = it; cad.path = it.optString("dxf")
        notice = "Saqlandi: AutoCAD DXF, PDF va rasm kompyuterda" + if (openOnPc) " — Chizmalar oynasida ochildi" else ""
        cadList()
    }
}

fun AppModel.cadOpenOnPc(path: String) = call(block = post("/api/v1/cad/open", JSONObject().put("path", path))) {
    notice = "Kompyuterdagi Chizmalar oynasida ochildi"
}
