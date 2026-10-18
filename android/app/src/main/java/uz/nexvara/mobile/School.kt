package uz.nexvara.mobile

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar
import java.util.UUID

/** Teacher and office tools: answer sheets, class journal, document templates, lesson schedule. */

data class OmrResult(val student: String, val right: Int, val total: Int, val percent: Double, val mark: Int,
                     val variant: Int, val wrong: List<Int>, val time: Double)

data class OmrSet(val id: String, val title: String, val questions: Int, val variants: Int,
                  val keys: Map<String, String>, val pdf: String, val results: List<OmrResult>)

data class JClass(val id: Int, val name: String, val students: Int)

data class JGrade(val id: Int, val subject: String, val day: String, val grade: Int)

data class JStudent(val id: Int, val name: String, val grades: List<JGrade>, val average: Double?, val count: Int)

data class JView(val id: Int, val name: String, val subjects: List<String>, val students: List<JStudent>)

data class TplField(val key: String, val label: String, val example: String)

data class DocTemplate(val id: String, val title: String, val group: String, val fields: List<TplField>)

data class Lesson(val id: String, val day: Int, val start: String, val title: String, val room: String)

object SchoolParse {
    private fun JSONArray?.objs(): List<JSONObject> =
        if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

    fun omrResult(o: JSONObject) = OmrResult(
        o.optString("student"), o.optInt("right"), o.optInt("total"), o.optDouble("percent", 0.0), o.optInt("mark"),
        o.optInt("variant", 1), o.optJSONArray("wrong")?.let { a -> (0 until a.length()).map { a.optInt(it) } }.orEmpty(),
        o.optDouble("time", 0.0),
    )

    fun omrSet(o: JSONObject): OmrSet {
        val k = o.optJSONObject("keys") ?: JSONObject()
        return OmrSet(o.optString("id"), o.optString("title"), o.optInt("questions"), o.optInt("variants", 1),
            k.keys().asSequence().associateWith { k.optString(it) }, o.optString("pdf"),
            o.optJSONArray("results").objs().map(::omrResult))
    }

    fun omrSets(o: JSONObject) = o.optJSONArray("sets").objs().map(::omrSet)

    fun classes(o: JSONObject) = o.optJSONArray("classes").objs().map { JClass(it.optInt("id"), it.optString("name"), it.optInt("students")) }

    fun jview(o: JSONObject) = JView(
        o.optInt("id"), o.optString("name"),
        o.optJSONArray("subjects")?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty(),
        o.optJSONArray("students").objs().map { s ->
            JStudent(s.optInt("id"), s.optString("name"),
                s.optJSONArray("grades").objs().map { JGrade(it.optInt("id"), it.optString("subject"), it.optString("day"), it.optInt("grade")) },
                if (s.isNull("average")) null else s.optDouble("average"), s.optInt("count"))
        },
    )

    fun templates(o: JSONObject) = o.optJSONArray("templates").objs().map { t ->
        DocTemplate(t.optString("id"), t.optString("title"), t.optString("group"),
            t.optJSONArray("fields").objs().map { TplField(it.optString("key"), it.optString("label"), it.optString("example")) })
    }
}

/** Lessons live on the phone (not secret, no PC needed): Monday = 0. */
class Schedule(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("nexvara_schedule", Context.MODE_PRIVATE)
    var lessons by mutableStateOf(load()); private set
    var remindMinutes by mutableStateOf(prefs.getInt("remind", 5)); private set

    private fun load(): List<Lesson> {
        val a = runCatching { JSONArray(prefs.getString("lessons", "[]")) }.getOrDefault(JSONArray())
        return (0 until a.length()).mapNotNull { a.optJSONObject(it) }.map {
            Lesson(it.optString("id"), it.optInt("day"), it.optString("start"), it.optString("title"), it.optString("room"))
        }.sortedWith(compareBy({ it.day }, { it.start }))
    }

    private fun save(list: List<Lesson>) {
        val a = JSONArray()
        list.forEach { a.put(JSONObject().put("id", it.id).put("day", it.day).put("start", it.start).put("title", it.title).put("room", it.room)) }
        prefs.edit().putString("lessons", a.toString()).apply()
        lessons = load()
    }

    fun add(day: Int, start: String, title: String, room: String) {
        require(start.matches(Regex("([01]?\\d|2[0-3]):[0-5]\\d"))) { "Vaqtni SS:DD ko‘rinishida yozing, masalan 08:30" }
        require(title.isNotBlank()) { "Dars nomini yozing" }
        save(lessons + Lesson(UUID.randomUUID().toString(), day, start.padStart(5, '0'), title.trim(), room.trim()))
    }

    fun remove(l: Lesson) = save(lessons.filter { it.id != l.id })

    fun setRemind(m: Int) { remindMinutes = m; prefs.edit().putInt("remind", m).apply() }

    fun today(): List<Lesson> = lessons.filter { it.day == todayIndex() }

    companion object {
        val DAYS = listOf("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")
        fun todayIndex(): Int = (Calendar.getInstance().get(Calendar.DAY_OF_WEEK) + 5) % 7
    }
}
