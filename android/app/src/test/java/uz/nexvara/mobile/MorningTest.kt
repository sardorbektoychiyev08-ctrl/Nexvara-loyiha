package uz.nexvara.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class MorningTest {
    @Test fun nextTimeIsTodayOrTomorrow() {
        val c = Calendar.getInstance().apply { set(2026, 9, 19, 6, 0, 0); set(Calendar.MILLISECOND, 0) }
        val at = Morning.next("07:30", c.timeInMillis)
        assertEquals(90 * 60_000L, at - c.timeInMillis)
        c.set(Calendar.HOUR_OF_DAY, 8)
        val tomorrow = Morning.next("07:30", c.timeInMillis)
        assertEquals((23 * 60 + 30) * 60_000L, tomorrow - c.timeInMillis)
    }

    @Test fun textHasLessonsInOrderAndPcState() {
        val l = listOf(Lesson("b", 0, "10:00", "Fizika", "12-xona"), Lesson("a", 0, "08:30", "Algebra", ""))
        val (title, lines) = Morning.text("Dushanba", l, listOf("⚠ Kecha 1 ta ish bajarilmadi: PDF"), false)
        assertEquals("Xayrli tong! Bugun Dushanba", title)
        assertEquals("   08:30 Algebra", lines[1])
        assertEquals("   10:00 Fizika (12-xona)", lines[2])
        assertTrue(lines.last().startsWith("⚠"))
        val off = Morning.text("Shanba", emptyList(), null, true).second
        assertEquals(listOf("📚 Bugun jadvalda dars yo‘q", "💻 Kompyuter o‘chiq yoki boshqa tarmoqda"), off)
    }
}

class CadColorTest {
    @Test fun paletteMatchesThePc() {
        assertEquals(0xFFEF4444, CadColors.argb(1))
        assertEquals(null, CadColors.argb(7))  // the theme's ink
        assertEquals(0xFFFF0000, CadColors.argb(10))  // hue 0, full colour
        assertEquals(0xFFFF8080, CadColors.argb(11))  // pastel
        assertEquals(0xFF333333, CadColors.argb(250))
        assertEquals("To‘q sariq", CadColors.name(30))
    }

    @Test fun colourSurvivesJson() {
        val s = CadState()
        s.color = 30
        s.add(CadE.Line(Pt(0.0, 0.0), Pt(10.0, 0.0)))
        s.color = CadColors.BY_LAYER
        s.add(CadE.Circle(Pt(0.0, 0.0), 5.0))
        val back = CadState(); back.load(s.toJson())
        assertEquals(30, back.colorOf[back.items[0]])
        assertEquals(null, back.colorOf[back.items[1]])
    }
}

class AiParseTest {
    @Test fun directionsFromThePc() {
        val o = org.json.JSONObject("""{"capabilities": {
          "tts": {"label": "Matn → ovoz (TTS)", "mode": "auto", "provider": "", "model": "",
                  "offers": {"gemini": {"label": "Google Gemini", "connected": true, "models": ["gemini-3.8-flash-lite-tts"]},
                             "openai": {"label": "OpenAI", "connected": false, "models": ["gpt-4o-mini-tts"]}},
                  "auto_pick": {"provider": "gemini", "model": "gemini-3.8-flash-lite-tts", "free": true}},
          "image": {"label": "Rasm", "mode": "manual", "provider": "openai", "model": "gpt-image-1-mini", "offers": {}, "auto_pick": null}}}""")
        val d = AiParse.directions(o)
        assertEquals(listOf("image", "tts"), d.map { it.id })  // the PC's order
        assertEquals("Google Gemini · gemini-3.8-flash-lite-tts (bepul)", d[1].autoPick)
        assertEquals(false, d[1].offers.first { it.provider == "openai" }.connected)
        assertEquals("gpt-image-1-mini", d[0].model)
    }
}
