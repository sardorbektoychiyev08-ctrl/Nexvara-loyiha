package uz.nexvara.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Finger strokes (with a little hand shake) become clean geometry; the JSON matches the PC. */
class CadTest {
    private fun shaky(i: Int) = sin(i * 1.7) * 0.6  // ±0.6 mm tremor

    @Test fun wobblyStrokeBecomesAStraightLevelLine() {
        val stroke = (0..40).map { Pt(it * 2.5, 10 + shaky(it) + it * 0.03) }  // ~1.7° slope
        val e = Recognizer.recognize(stroke, 2.0, tidy = true)
        assertTrue(e is CadE.Line)
        e as CadE.Line
        assertEquals(e.a.y, e.b.y, 1e-6)  // snapped to horizontal
        assertEquals(100.0, e.a.dist(e.b), 2.0)
    }

    @Test fun roughLoopBecomesACircle() {
        val stroke = (0..60).map { val a = 2 * PI * it / 60; Pt(50 + (30 + shaky(it)) * cos(a), 40 + (30 + shaky(it)) * sin(a)) }
        val e = Recognizer.recognize(stroke, 2.0, tidy = true)
        assertTrue(e is CadE.Circle)
        e as CadE.Circle
        assertEquals(30.0, e.r, 1.0)
        assertEquals(50.0, e.c.x, 1.0)
    }

    @Test fun roughBoxBecomesAnExactRectangle() {
        val corners = listOf(Pt(0.0, 0.0), Pt(80.0, 1.5), Pt(79.0, 50.0), Pt(-1.0, 49.0), Pt(0.5, 0.5))
        val stroke = corners.zipWithNext().flatMap { (a, b) -> (0 until 20).map { k -> Pt(a.x + (b.x - a.x) * k / 20 + shaky(k) * 0.3, a.y + (b.y - a.y) * k / 20) } }
        val e = Recognizer.recognize(stroke, 2.0, tidy = true)
        assertTrue("got $e", e is CadE.Poly && e.closed && e.pts.size == 4)
        e as CadE.Poly
        assertEquals(2, e.pts.map { it.x }.distinct().size)  // axis-aligned
        assertEquals(2, e.pts.map { it.y }.distinct().size)
    }

    @Test fun curvedStrokeBecomesAnArc() {
        val stroke = (0..30).map { val a = PI * it / 30; Pt(40 * cos(a), 40 * sin(a)) }  // upper half, right to left
        val e = Recognizer.recognize(stroke, 2.0, tidy = true)
        assertTrue("got $e", e is CadE.Arc)
        e as CadE.Arc
        assertEquals(40.0, e.r, 0.5)
        assertEquals(180.0, CadGeom.sweep(e.start, e.end), 3.0)
    }

    @Test fun drawingJsonRoundTrip() {
        val s = CadState()
        s.add(CadE.Line(Pt(0.0, 0.0), Pt(100.0, 0.0)))
        s.add(CadE.Circle(Pt(50.0, 30.0), 10.0))
        s.add(CadE.Dim(Pt(0.0, 0.0), Pt(100.0, 0.0), Pt(50.0, -12.0), 0.0))
        s.add(CadE.Text(Pt(0.0, 50.0), "Plastina", 3.5))
        val json = s.toJson()
        assertEquals(4, json.getJSONArray("entities").length())
        assertEquals("ldim", json.getJSONArray("entities").getJSONObject(2).getString("type"))
        val back = CadState(); back.load(json)
        assertEquals(s.items.toList(), back.items.toList())
        s.undo(); assertEquals(3, s.items.size); s.redo(); assertEquals(4, s.items.size)
    }
}
