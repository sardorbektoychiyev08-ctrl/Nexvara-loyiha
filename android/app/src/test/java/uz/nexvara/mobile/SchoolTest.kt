package uz.nexvara.mobile

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import uz.nexvara.mobile.ui.Lang
import uz.nexvara.mobile.ui.tr
import java.util.Calendar

class SchoolTest {
    private fun at(year: Int, month: Int, day: Int, h: Int, m: Int): Long =
        Calendar.getInstance().apply { set(year, month - 1, day, h, m, 0); set(Calendar.MILLISECOND, 0) }.timeInMillis

    @Test fun nextLessonReminder() {
        // 2026-10-19 is a Monday (day 0); the lesson is Monday 08:30, reminder 5 minutes before.
        val l = Lesson("a", 0, "08:30", "7-B fizika", "12")
        val sunday = at(2026, 10, 18, 20, 0)
        val (lesson, time) = Reminders.nextLesson(listOf(l), 5, sunday)!!
        assertEquals("7-B fizika", lesson.title)
        assertEquals(at(2026, 10, 19, 8, 25), time)
        // After the lesson started: next week's Monday.
        val (_, next) = Reminders.nextLesson(listOf(l), 5, at(2026, 10, 19, 9, 0))!!
        assertEquals(at(2026, 10, 26, 8, 25), next)
        assertNull(Reminders.nextLesson(emptyList(), 5, sunday))
    }

    @Test fun dictationPiecesBecomeSentences() {
        assertEquals("Majlis boshlandi.", sentence("majlis boshlandi"))
        assertEquals("Kim qarshi?", sentence(" kim qarshi? "))
        assertEquals("", sentence("  "))
    }

    @Test fun parsesAnswerSheetsAndJournal() {
        val sets = SchoolParse.omrSets(JSONObject("""{"sets":[{"id":"ab12","title":"7-B","questions":20,"variants":2,
            "keys":{"1":"ABCD"},"pdf":"D:\\x.pdf","results":[{"student":"Vali","right":18,"total":20,"percent":90.0,
            "mark":5,"variant":1,"wrong":[3,7],"time":1}]}]}"""))
        assertEquals(5, sets[0].results[0].mark)
        assertEquals(listOf(3, 7), sets[0].results[0].wrong)
        val v = SchoolParse.jview(JSONObject("""{"id":1,"name":"7-B","subjects":["Fizika"],"students":[
            {"id":5,"name":"Ali","grades":[{"id":1,"subject":"Fizika","day":"2026-10-17","grade":5}],"average":5.0,"count":1},
            {"id":6,"name":"Vali","grades":[],"average":null,"count":0}]}"""))
        assertEquals(5.0, v.students[0].average!!, 0.0)
        assertNull(v.students[1].average)
    }

    @Test fun russianInterfaceKeepsCommandsUzbek() {
        Lang.ru = true
        try {
            assertEquals("Главная", tr("Bosh sahifa"))
            assertEquals("Готовые команды", tr("Tayyor buyruqlar"))
            // A ready command is sent to the PC as it is: never translated.
            val cmd = "7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber"
            assertEquals(cmd, tr(cmd))
        } finally { Lang.ru = false }
        assertTrue(tr("Bosh sahifa") == "Bosh sahifa")
    }
}
