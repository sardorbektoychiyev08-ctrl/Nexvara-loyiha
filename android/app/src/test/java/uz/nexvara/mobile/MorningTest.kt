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
