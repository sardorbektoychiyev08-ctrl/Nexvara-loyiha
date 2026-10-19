package uz.nexvara.mobile

import android.app.Application
import android.graphics.Bitmap
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

/** What the teacher/office tool screens show. */
class Tools {
    var omrSets by mutableStateOf<List<OmrSet>>(emptyList())
    var lastTest by mutableStateOf<Pair<Int, Int>?>(null)  // questions, variants of the last generated test
    var omrLast by mutableStateOf<OmrResult?>(null)
    var classes by mutableStateOf<List<JClass>>(emptyList())
    var jview by mutableStateOf<JView?>(null)
    var jSubject by mutableStateOf("")
    var templates by mutableStateOf<List<DocTemplate>>(emptyList())
    var ocrText by mutableStateOf<String?>(null)
    var ocrPath by mutableStateOf<String?>(null)  // the uploaded photo the text came from
    var ocrRaw by mutableStateOf("")
    var preview by mutableStateOf<Preview?>(null)
    var autostart by mutableStateOf<Boolean?>(null)
    var controlOn by mutableStateOf(false)
    var touchpad by mutableStateOf(true)  // finger moves the cursor, like a laptop touchpad
    var dragging by mutableStateOf(false)
    var dictating by mutableStateOf(false)
    var dictation by mutableStateOf("")
    var partial by mutableStateOf("")
}

sealed class Preview(val title: String) {
    class Pdf(title: String, val file: File) : Preview(title)
    class Image(title: String, val bitmap: Bitmap) : Preview(title)
    class Text(title: String, val text: String) : Preview(title)
}

private fun enc(s: String) = java.net.URLEncoder.encode(s, "UTF-8")

// ---------------- answer sheets ----------------
fun AppModel.loadOmr() = call(quiet = tools.omrSets.isNotEmpty(), block = get("/api/v1/omr")) {
    tools.omrSets = SchoolParse.omrSets(it)
    tools.lastTest = it.optJSONObject("last_test")?.let { t -> t.optInt("questions") to t.optInt("variants") }
}

fun AppModel.createSheet(title: String, questions: Int, variants: Int, key: String, copies: Int, fromLastTest: Boolean) {
    val b = JSONObject().put("title", title).put("questions", questions).put("variants", variants).put("copies", copies)
    if (fromLastTest) b.put("from_last_test", true)
    else if (key.isNotBlank()) b.put("keys", JSONObject().put("1", key))
    call(block = post("/api/v1/omr", b)) {
        notice = "Varaqa tayyor — kompyuterda ochildi, chop eting"
        loadOmr()
    }
}

fun AppModel.setOmrKey(set: OmrSet, variant: Int, key: String) =
    call(block = post("/api/v1/omr/${set.id}/keys", JSONObject().put("keys", JSONObject(set.keys).put(variant.toString(), key)))) {
        notice = "Kalit saqlandi"; loadOmr()
    }

fun AppModel.gradeSheet(set: OmrSet, photoPath: String, student: String) =
    call(block = post("/api/v1/omr/${set.id}/grade", JSONObject().put("path", photoPath).put("student", student))) {
        val r = SchoolParse.omrResult(it)
        tools.omrLast = r
        notice = "${r.student}: baho ${r.mark} — ${r.right}/${r.total} to‘g‘ri (${r.percent}%)"
        loadOmr()
    }

// ---------------- class journal ----------------
fun AppModel.loadJournal() = call(quiet = tools.classes.isNotEmpty(), block = get("/api/v1/journal")) {
    tools.classes = SchoolParse.classes(it)
}

fun AppModel.addClass(name: String) = call(block = post("/api/v1/journal", JSONObject().put("name", name))) {
    tools.classes = SchoolParse.classes(it)
}

fun AppModel.openClass(id: Int, subject: String = tools.jSubject) =
    call(block = get("/api/v1/journal/$id?subject=${enc(subject)}")) { tools.jview = SchoolParse.jview(it) }

fun AppModel.addStudents(id: Int, names: String) =
    call(block = post("/api/v1/journal/$id/students", JSONObject().put("names", names))) {
        notice = "${it.optInt("added")} ta o‘quvchi qo‘shildi"; openClass(id); loadJournal()
    }

fun AppModel.putGrade(student: JStudent, grade: Int, subject: String) =
    call(quiet = true, block = post("/api/v1/journal/grade",
        JSONObject().put("student_id", student.id).put("grade", grade).put("subject", subject))) {
        notice = "${student.name}: $grade"
        tools.jview?.let { v -> openClass(v.id) }
    }

fun AppModel.deleteClass(id: Int) = call(block = post("/api/v1/journal/$id/delete")) {
    tools.classes = SchoolParse.classes(it); tools.jview = null
}

fun AppModel.exportJournal(id: Int, then: (String) -> Unit = {}) =
    call(block = post("/api/v1/journal/$id/export", JSONObject().put("open_on_pc", true))) {
        notice = "Excel jurnal kompyuterda ochildi"; then(it.optString("path"))
    }

// ---------------- document templates ----------------
fun AppModel.loadTemplates() = call(quiet = tools.templates.isNotEmpty(), block = get("/api/v1/doctemplates")) {
    tools.templates = SchoolParse.templates(it)
}

fun AppModel.makeDocument(t: DocTemplate, fields: Map<String, String>, background: Boolean) =
    call(block = post("/api/v1/doctemplates/${t.id}", JSONObject().put("fields", JSONObject(fields)).put("background", background))) {
        notice = "${t.title}: Word kompyuterda yozmoqda"
        refreshTasks(); open(Screen.Tasks)
    }

// ---------------- photo → text ----------------
fun AppModel.ocr(path: String, lang: String = "") = call(block = post("/api/v1/ocr", JSONObject().put("path", path).put("lang", lang))) {
    tools.ocrPath = path
    tools.ocrRaw = it.optString("text")
    tools.ocrText = it.optString("text").ifBlank { "(matn topilmadi — suratni yaqinroq va yorug‘roq oling)" }
}

/** The photo's text → an Excel table (opened here as a preview) or a Word document (a PC task). */
fun AppModel.ocrConvert(to: String) {
    val path = tools.ocrPath ?: return
    val body = JSONObject().put("path", path).put("to", to).put("text", tools.ocrRaw)
    call(block = post("/api/v1/ocr/convert", body)) {
        if (to == "excel") {
            notice = "Excel jadval tayyor: ${it.optInt("rows")} qator, ${it.optInt("cols")} ustun"
            previewFile(it.optString("path"))
        } else {
            notice = "Word hujjat kompyuterda yozilmoqda"
            refreshTasks(); open(Screen.Tasks)
        }
    }
}

// ---------------- preview inside the app ----------------
fun AppModel.previewFile(path: String) {
    val ctx = getApplication<Application>()
    val name = TransferChecks.resultFileName(path)
    call(block = { a -> a.bytes("/api/v1/files/preview?path=${enc(path)}") }) { data ->
        tools.preview = when {
            data.size > 4 && String(data, 0, 4, Charsets.ISO_8859_1) == "%PDF" -> {
                ctx.cacheDir.listFiles { f -> f.name.startsWith("preview-") }?.forEach { it.delete() }
                val f = File(ctx.cacheDir, "preview-${System.currentTimeMillis()}.pdf").apply { writeBytes(data) }
                Preview.Pdf(name, f)
            }
            data.size > 3 && (data[0] == 0xFF.toByte() || data[0] == 0x89.toByte()) ->
                android.graphics.BitmapFactory.decodeByteArray(data, 0, data.size)?.let { Preview.Image(name, it) }
                    ?: Preview.Text(name, "Rasmni ochib bo‘lmadi")
            else -> Preview.Text(name, String(data, Charsets.UTF_8).take(200_000))
        }
        open(Screen.Preview)
    }
}

// ---------------- the PC: control, autostart, wake ----------------
fun AppModel.control(action: String, x: Float? = null, y: Float? = null, dy: Int = 0, text: String = "", key: String = "", dx: Int = 0) {
    val b = JSONObject().put("action", action).put("dy", dy).put("dx", dx).put("text", text).put("key", key)
    if (x != null && y != null) b.put("x", x.toDouble()).put("y", y.toDouble())
    call(quiet = true, block = post("/api/v1/control", b)) { }
}

fun AppModel.loadAutostart() = call(quiet = true, block = get("/api/v1/autostart")) { tools.autostart = it.optBoolean("on") }

fun AppModel.setAutostart(on: Boolean) = call(block = post("/api/v1/autostart", JSONObject().put("on", on))) {
    tools.autostart = it.optBoolean("on")
    notice = if (it.optBoolean("on")) "NEXVARA endi Windows bilan birga ishga tushadi" else "Avtomatik ishga tushish o‘chirildi"
}

val AppModel.canWake: Boolean get() = profile?.optJSONObject("wake")?.optString("mac")?.isNotBlank() == true

fun AppModel.wakePc() {
    val w = profile?.optJSONObject("wake") ?: run { notice = "Avval kompyuter yoqiq paytda bir marta ulaning"; return }
    viewModelScope.launch {
        try {
            withContext(Dispatchers.IO) { Wake.send(w.optString("mac"), w.optString("broadcast")) }
            notice = "Uyg‘otish signali yuborildi. Kompyuter 30–60 soniyada yoqiladi (Wake-on-LAN yoqilgan bo‘lsa)."
        } catch (e: Exception) {
            notice = "Signal yuborilmadi: telefon kompyuter bilan bir Wi-Fi’da bo‘lsin"
        }
    }
}

// ---------------- meeting notes (dictation) ----------------
/** A recognised piece of speech as a sentence: capital first letter, closing period. */
fun sentence(piece: String): String {
    val t = piece.trim()
    if (t.isEmpty()) return t
    val first = t.substring(0, 1).uppercase() + t.substring(1)
    return if (first.last() in ".!?…:;") first else "$first."
}

fun AppModel.polishDictation() {
    val text = tools.dictation.trim()
    if (text.isEmpty()) return
    send(("AI bilan quyidagi matndagi imlo va tinish belgilarini tuzat, xatboshilarga ajrat, ma’nosini o‘zgartirma: $text").take(4000))
    open(Screen.Chat)
}
fun AppModel.sendDictation(asMinutes: Boolean) {
    val text = tools.dictation.trim()
    if (text.isEmpty()) { notice = "Hali hech narsa yozilmadi"; return }
    if (asMinutes) {
        send(("AI bilan quyidagi yozuvdan majlis bayonnomasini tuz (qatnashchilar, muhokama, qarorlar): $text").take(4000))
        open(Screen.Chat)
        return
    }
    // As a text file on the PC (it becomes the chat's "shu fayl").
    val ctx = getApplication<Application>()
    val dir = File(ctx.cacheDir, "camera").apply { mkdirs() }
    val f = File(dir, "Majlis ${java.text.SimpleDateFormat("yyyy-MM-dd HH-mm", java.util.Locale.US).format(java.util.Date())}.txt")
    f.writeText(text)
    upload(androidx.core.content.FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", f))
}
