package uz.nexvara.mobile.ui

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Redo
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import uz.nexvara.mobile.*
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin

/** Drawing tools on the phone. "Smart pen" recognises what the finger drew. */
private enum class CadTool(val label: String) {
    Smart("Aqlli qalam"), Line("Chiziq"), Rect("To‘rtburchak"), Circle("Aylana"),
    Dim("O‘lcham"), Text("Matn"), Edit("O‘zgartirish"), Erase("O‘chirgich"),
}

private fun fmt(v: Double) = (Math.round(v * 10) / 10.0).toString().removeSuffix(".0").replace('.', ',')

@Composable
fun CadScreen(m: AppModel) {
    val cad = m.cad
    val x = LocalExtra.current
    var tool by remember { mutableStateOf(CadTool.Smart) }
    var tidy by remember { mutableStateOf(true) }
    var scale by remember { mutableFloatStateOf(3f) }  // px per mm
    var origin by remember { mutableStateOf(Offset.Zero) }  // screen position of model (0,0)
    var size by remember { mutableStateOf(Size.Zero) }
    val stroke = remember { mutableStateListOf<Offset>() }
    var textAt by remember { mutableStateOf<Pt?>(null) }
    var editIdx by remember { mutableStateOf<Int?>(null) }
    var saveDialog by remember { mutableStateOf(false) }
    var listDialog by remember { mutableStateOf(false) }
    val ink = MaterialTheme.colorScheme.onSurface
    val accent = MaterialTheme.colorScheme.primary
    val grid = x.muted.copy(alpha = 0.18f)

    fun toModel(o: Offset) = Pt(((o.x - origin.x) / scale).toDouble(), ((origin.y - o.y) / scale).toDouble())
    fun toScreen(p: Pt) = Offset(origin.x + p.x.toFloat() * scale, origin.y - p.y.toFloat() * scale)
    val tolMm = 10.0 / scale  // a finger is ~10 px precise
    fun snap(p: Pt): Pt {
        var best: Pt? = null; var bd = 18.0 / scale
        cad.items.forEach { e -> CadGeom.ends(e).forEach { q -> val d = q.dist(p); if (d < bd) { bd = d; best = q } } }
        return best ?: p
    }
    fun pick(p: Pt): Int? = cad.items.indices.minByOrNull { CadGeom.distance(cad.items[it], p) }
        ?.takeIf { CadGeom.distance(cad.items[it], p) < 20.0 / scale }

    fun fit() {
        if (size == Size.Zero) return
        val pts = cad.items.flatMap { CadGeom.ends(it) + when (it) {
            is CadE.Circle -> listOf(it.c + Pt(it.r, it.r), it.c - Pt(it.r, it.r)); else -> emptyList() } }
        if (pts.isEmpty()) { scale = 3f; origin = Offset(size.width * 0.15f, size.height * 0.8f); return }
        val x1 = pts.minOf { it.x }; val x2 = pts.maxOf { it.x }; val y1 = pts.minOf { it.y }; val y2 = pts.maxOf { it.y }
        scale = min((size.width * 0.85f) / max(x2 - x1, 1.0).toFloat(), (size.height * 0.85f) / max(y2 - y1, 1.0).toFloat()).coerceIn(0.05f, 200f)
        origin = Offset(size.width / 2 - ((x1 + x2) / 2).toFloat() * scale, size.height / 2 + ((y1 + y2) / 2).toFloat() * scale)
    }

    fun finish(points: List<Offset>) {
        if (points.isEmpty()) return
        val pts = points.map { toModel(it) }
        val a = snap(pts.first()); val b = snap(pts.last())
        when (tool) {
            CadTool.Smart -> Recognizer.recognize(pts, tolMm, tidy)?.let { e ->
                cad.add(when (e) {  // glue line ends to nearby points
                    is CadE.Line -> CadE.Line(snap(e.a), snap(e.b))
                    is CadE.Poly -> if (e.closed) e else CadE.Poly(listOf(snap(e.pts.first())) + e.pts.drop(1).dropLast(1) + snap(e.pts.last()), false)
                    else -> e
                })
            }
            CadTool.Line -> if (a.dist(b) > tolMm) cad.add(CadE.Line(a, if (tidy) Recognizer.snapAngle(a, b) else b))
            CadTool.Rect -> if (abs(a.x - b.x) > tolMm && abs(a.y - b.y) > tolMm)
                cad.add(CadE.Poly(listOf(a, Pt(b.x, a.y), b, Pt(a.x, b.y)), true))
            CadTool.Circle -> if (a.dist(b) > tolMm) cad.add(CadE.Circle(a, CadGeom.round1(a.dist(b))))
            CadTool.Dim -> if (a.dist(b) > tolMm) {
                val vertical = abs(b.x - a.x) < abs(b.y - a.y)
                val off = 12.0
                val base = if (vertical) Pt(max(a.x, b.x) + off, (a.y + b.y) / 2) else Pt((a.x + b.x) / 2, min(a.y, b.y) - off)
                cad.add(CadE.Dim(a, b, base, if (vertical) 90.0 else 0.0))
            }
            CadTool.Text -> textAt = a
            CadTool.Edit -> editIdx = pick(pts.first())
            CadTool.Erase -> {
                val hit = pts.mapNotNull { pick(it) }.distinct().sortedDescending()
                if (hit.isNotEmpty()) { cad.snapshot(); hit.forEach { cad.items.removeAt(it) } }
            }
        }
    }

    LaunchedEffect(Unit) { m.cadList() }
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Chizma", cad.name + if (cad.path != null) " · kompyuterda saqlangan" else "", onBack = { m.goBack() }) {
            IconButton(onClick = { m.cadList(); listDialog = true }) { Icon(Icons.Default.FolderOpen, "Kompyuterdagi chizmalar") }
            IconButton(onClick = { saveDialog = true }) { Icon(Icons.Default.Save, "Saqlash") }
        }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = Gutter),
            horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            CadTool.entries.forEach { t ->
                FilterChip(selected = tool == t, onClick = { tool = t }, label = { Text(t.label) })
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth().padding(8.dp).background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))) {
            Canvas(Modifier.fillMaxSize().pointerInput(tool, tidy, scale, origin) {
                awaitEachGesture {
                    val down = awaitFirstDown()
                    var multi = false
                    stroke.clear(); stroke.add(down.position)
                    while (true) {
                        val ev = awaitPointerEvent()
                        val pressed = ev.changes.filter { it.pressed }
                        if (pressed.isEmpty()) break
                        if (pressed.size >= 2) {  // two fingers: zoom and move the sheet
                            multi = true; stroke.clear()
                            val zoom = ev.calculateZoom(); val pan = ev.calculatePan(); val c = ev.calculateCentroid()
                            val newScale = (scale * zoom).coerceIn(0.05f, 300f)
                            origin = Offset(c.x - (c.x - origin.x) * (newScale / scale) + pan.x, c.y - (c.y - origin.y) * (newScale / scale) + pan.y)
                            scale = newScale
                        } else if (!multi) stroke.add(pressed[0].position)
                        ev.changes.forEach { it.consume() }
                    }
                    if (!multi) finish(stroke.toList())
                    stroke.clear()
                }
            }) {
                if (size != this.size) { val first = size == Size.Zero; size = this.size; if (first) fit() }
                drawGrid(scale, origin, grid)
                cad.items.forEachIndexed { i, e -> drawEntity(e, ::toScreen, scale, if (i == editIdx) accent else ink) }
                if (stroke.size > 1) {
                    for (k in 1 until stroke.size) drawLine(accent, stroke[k - 1], stroke[k], 3f, StrokeCap.Round)
                    val a = toModel(stroke.first()); val b = toModel(stroke.last())
                    val label = when (tool) {
                        CadTool.Circle -> "R ${fmt(a.dist(b))} mm"
                        CadTool.Rect -> "${fmt(abs(b.x - a.x))} × ${fmt(abs(b.y - a.y))} mm"
                        else -> "${fmt(a.dist(b))} mm"
                    }
                    drawLabel(label, stroke.last() + Offset(24f, -24f), accent, 40f)
                }
            }
            Text(when (tool) {
                CadTool.Smart -> "Barmoq bilan chizing: chiziq, to‘rtburchak, aylana, yoy o‘zi tekislanadi. Ikki barmoq — kattalashtirish."
                CadTool.Dim -> "Ikki nuqta orasini torting — o‘lcham qo‘yiladi"
                CadTool.Edit -> "Obyektni bosing — aniq o‘lchamini yozing"
                CadTool.Erase -> "O‘chiriladigan obyekt ustidan suring"
                CadTool.Text -> "Matn joyini bosing"
                else -> "Boshlanish nuqtasidan oxirigacha torting"
            }, style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(8.dp))
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            IconButton(onClick = { cad.undo() }, enabled = cad.undo.isNotEmpty()) { Icon(Icons.AutoMirrored.Filled.Undo, "Orqaga") }
            IconButton(onClick = { cad.redo() }, enabled = cad.redo.isNotEmpty()) { Icon(Icons.AutoMirrored.Filled.Redo, "Qaytarish") }
            IconButton(onClick = { fit() }) { Icon(Icons.Default.FitScreen, "Hammasini ko‘rsatish") }
            FilterChip(selected = tidy, onClick = { tidy = !tidy }, label = { Text("Tekislash") })
            IconButton(onClick = { cad.clear() }) { Icon(Icons.Default.DeleteSweep, "Tozalash") }
            Text("${cad.items.size} ta", style = MaterialTheme.typography.bodySmall, color = x.muted,
                modifier = Modifier.align(androidx.compose.ui.Alignment.CenterVertically))
        }
    }

    textAt?.let { at ->
        var t by remember { mutableStateOf("") }
        var h by remember { mutableStateOf("3,5") }
        AlertDialog(onDismissRequest = { textAt = null }, title = { Text("Matn") },
            text = { Column {
                OutlinedTextField(t, { t = it }, label = { Text("Matn") })
                OutlinedTextField(h, { h = it }, label = { Text("Balandligi, mm") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
            } },
            confirmButton = { TextButton(onClick = {
                if (t.isNotBlank()) cad.add(CadE.Text(at, t, h.replace(',', '.').toDoubleOrNull() ?: 3.5)); textAt = null
            }) { Text("Qo‘shish") } },
            dismissButton = { TextButton(onClick = { textAt = null }) { Text("Bekor") } })
    }

    editIdx?.let { i -> if (i in cad.items.indices) EditDialog(cad.items[i], onDone = { e -> if (e != null) cad.replace(i, e); editIdx = null },
        onDelete = { cad.remove(i); editIdx = null }) else editIdx = null }

    if (saveDialog) {
        var name by remember { mutableStateOf(cad.name) }
        var openPc by remember { mutableStateOf(true) }
        AlertDialog(onDismissRequest = { saveDialog = false }, title = { Text("Kompyuterga saqlash") },
            text = { Column {
                OutlinedTextField(name, { name = it }, label = { Text("Nomi") })
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Checkbox(openPc, { openPc = it }); Text("Kompyuterdagi Chizmalar oynasida ochish")
                }
                Text("AutoCAD DXF (mm), PDF va rasm bo‘lib saqlanadi.", style = MaterialTheme.typography.bodySmall, color = x.muted)
            } },
            confirmButton = { TextButton(onClick = { cad.name = name.ifBlank { "Telefon chizmasi" }; m.cadSave(openPc); saveDialog = false }) { Text("Saqlash") } },
            dismissButton = { TextButton(onClick = { saveDialog = false }) { Text("Bekor") } })
    }

    if (listDialog) {
        AlertDialog(onDismissRequest = { listDialog = false }, title = { Text("Kompyuterdagi chizmalar") },
            text = {
                if (cad.drawings.isEmpty()) Text("Hali chizma yo‘q", color = x.muted)
                else LazyColumn(Modifier.heightIn(max = 380.dp)) {
                    items(cad.drawings) { (name, path) ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Text(name, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                            TextButton(onClick = { m.cadLoad(path); listDialog = false; fit() }) { Text("Ochish") }
                            IconButton(onClick = { m.cadOpenOnPc(path) }) { Icon(Icons.Default.Computer, "Kompyuterda ochish") }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { listDialog = false }) { Text("Yopish") } })
    }
}

@Composable
private fun EditDialog(e: CadE, onDone: (CadE?) -> Unit, onDelete: () -> Unit) {
    fun d(v: Double) = fmt(v)
    val fields = remember(e) {
        mutableStateListOf<Pair<String, String>>().apply {
            when (e) {
                is CadE.Line -> { add("Uzunlik, mm" to d(e.a.dist(e.b))); add("Burchak, °" to d(Math.toDegrees(kotlin.math.atan2(e.b.y - e.a.y, e.b.x - e.a.x)))) }
                is CadE.Circle -> add("Radius, mm" to d(e.r))
                is CadE.Arc -> add("Radius, mm" to d(e.r))
                is CadE.Poly -> if (e.closed && e.pts.size == 4) {
                    add("Eni, mm" to d(e.pts.maxOf { it.x } - e.pts.minOf { it.x })); add("Bo‘yi, mm" to d(e.pts.maxOf { it.y } - e.pts.minOf { it.y }))
                }
                is CadE.Text -> { add("Matn" to e.text); add("Balandligi, mm" to d(e.h)) }
                is CadE.Dim -> add("O‘lchov" to d(CadGeom.dimValue(e)))
            }
        }
    }
    fun num(i: Int) = fields.getOrNull(i)?.second?.replace(',', '.')?.toDoubleOrNull()
    AlertDialog(onDismissRequest = { onDone(null) }, title = { Text("Aniq o‘lcham") },
        text = { Column {
            if (fields.isEmpty()) Text("Bu obyekt uchun raqamli o‘lcham yo‘q (faqat o‘chirish mumkin)")
            fields.forEachIndexed { i, (label, value) ->
                OutlinedTextField(value, { fields[i] = label to it }, label = { Text(label) }, enabled = e !is CadE.Dim,
                    keyboardOptions = KeyboardOptions(keyboardType = if (label == "Matn") KeyboardType.Text else KeyboardType.Decimal))
            }
        } },
        confirmButton = { TextButton(onClick = {
            val out: CadE? = when (e) {
                is CadE.Line -> { val l = num(0); val a = num(1)
                    if (l != null && l > 0 && a != null) { val r = Math.toRadians(a); CadE.Line(e.a, Pt(e.a.x + l * cos(r), e.a.y + l * sin(r))) } else null }
                is CadE.Circle -> num(0)?.takeIf { it > 0 }?.let { CadE.Circle(e.c, it) }
                is CadE.Arc -> num(0)?.takeIf { it > 0 }?.let { e.copy(r = it) }
                is CadE.Poly -> { val w = num(0); val h = num(1)
                    if (w != null && h != null && w > 0 && h > 0) { val o = Pt(e.pts.minOf { it.x }, e.pts.minOf { it.y })
                        CadE.Poly(listOf(o, Pt(o.x + w, o.y), Pt(o.x + w, o.y + h), Pt(o.x, o.y + h)), true) } else null }
                is CadE.Text -> CadE.Text(e.p, fields[0].second, num(1) ?: e.h)
                is CadE.Dim -> null
            }
            onDone(out)
        }) { Text("Qo‘llash") } },
        dismissButton = { TextButton(onClick = onDelete) { Text("O‘chirish") } })
}

private fun DrawScope.drawGrid(scale: Float, origin: Offset, color: Color) {
    val target = 40f / scale  // ~40 px between lines
    val p = 10.0.pow(floor(log10(target.toDouble()))).toFloat()
    val step = listOf(1f, 2f, 5f, 10f).map { it * p }.first { it * scale >= 30f } * scale
    var gx = origin.x % step; while (gx < size.width) { drawLine(color, Offset(gx, 0f), Offset(gx, size.height), 1f); gx += step }
    var gy = origin.y % step; while (gy < size.height) { drawLine(color, Offset(0f, gy), Offset(size.width, gy), 1f); gy += step }
    drawLine(color.copy(alpha = 0.6f), Offset(origin.x, 0f), Offset(origin.x, size.height), 1.5f)
    drawLine(color.copy(alpha = 0.6f), Offset(0f, origin.y), Offset(size.width, origin.y), 1.5f)
}

private fun DrawScope.drawLabel(text: String, at: Offset, color: Color, px: Float) {
    val paint = Paint().apply { this.color = color.toArgb(); textSize = px; isAntiAlias = true }
    drawContext.canvas.nativeCanvas.drawText(text, at.x, at.y, paint)
}

private fun DrawScope.drawEntity(e: CadE, s: (Pt) -> Offset, scale: Float, color: Color) {
    val w = 3f
    when (e) {
        is CadE.Line -> drawLine(color, s(e.a), s(e.b), w, StrokeCap.Round)
        is CadE.Poly -> {
            e.pts.zipWithNext().forEach { (a, b) -> drawLine(color, s(a), s(b), w, StrokeCap.Round) }
            if (e.closed && e.pts.size > 2) drawLine(color, s(e.pts.last()), s(e.pts.first()), w, StrokeCap.Round)
        }
        is CadE.Circle -> drawCircle(color, e.r.toFloat() * scale, s(e.c), style = Stroke(w))
        is CadE.Arc -> {
            val r = e.r.toFloat() * scale; val c = s(e.c)
            drawArc(color, -e.end.toFloat(), CadGeom.sweep(e.start, e.end).toFloat(), false,
                topLeft = Offset(c.x - r, c.y - r), size = Size(2 * r, 2 * r), style = Stroke(w))
        }
        is CadE.Text -> drawLabel(e.text, s(e.p), color, max(18f, e.h.toFloat() * scale / 0.7f))
        is CadE.Dim -> {
            val r = Math.toRadians(e.rot); val u = Pt(cos(r), sin(r))
            fun proj(p: Pt): Pt { val t = (p.x - e.base.x) * u.x + (p.y - e.base.y) * u.y; return Pt(e.base.x + u.x * t, e.base.y + u.y * t) }
            val a = proj(e.a); val b = proj(e.b)
            val thin = color.copy(alpha = 0.75f)
            drawLine(thin, s(e.a), s(a), 1.5f); drawLine(thin, s(e.b), s(b), 1.5f)
            drawLine(thin, s(a), s(b), 1.5f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(1f, 0f)))
            listOf(a to b, b to a).forEach { (tip, from) ->
                val ts = s(tip); val fs = s(from); val ang = kotlin.math.atan2(ts.y - fs.y, ts.x - fs.x)
                for (sgn in listOf(-1, 1)) drawLine(thin, ts, Offset(ts.x - 18f * cos(ang + sgn * 0.35f), ts.y - 18f * sin(ang + sgn * 0.35f)), 2f)
            }
            val mid = s(Pt((a.x + b.x) / 2, (a.y + b.y) / 2))
            drawLabel(fmt(CadGeom.dimValue(e)), mid + Offset(-20f, -10f), color, 34f)
        }
    }
}
