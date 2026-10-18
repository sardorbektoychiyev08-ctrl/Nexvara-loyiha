package uz.nexvara.mobile.ui

import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import uz.nexvara.mobile.*

@Composable
private fun Screen(m: AppModel, title: String, subtitle: String? = null, actions: @Composable RowScope.() -> Unit = {},
                   content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit) {
    Column(Modifier.fillMaxSize()) {
        ScreenHeader(title, subtitle, onBack = { m.goBack() }, actions = actions)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = Gutter, end = Gutter, bottom = 28.dp, top = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

private fun markColor(mark: Int, x: Extra) = when (mark) { 5 -> x.success; 4 -> Color(0xFF0EA5E9); 3 -> x.warning; else -> x.danger }

/** 1 -> "A": the same letters as on the printed answer sheet and in the Word test. */
fun variantLetter(v: Int): String = if (v in 1..6) "ABCDEF"[v - 1].toString() else v.toString()

// ---------------- answer sheets ----------------
@Composable
fun AnswerSheetsScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val t = m.tools
    LaunchedEffect(Unit) { m.loadOmr() }
    var title by rememberSaveable { mutableStateOf("") }
    var n by rememberSaveable { mutableStateOf("20") }
    var variants by rememberSaveable { mutableStateOf(1) }
    var key by rememberSaveable { mutableStateOf("") }
    var copies by rememberSaveable { mutableStateOf("30") }
    var student by rememberSaveable { mutableStateOf("") }
    var keyFor by remember { mutableStateOf<OmrSet?>(null) }
    Screen(m, "Javob varaqalari", "Chop eting → o‘quvchilar bo‘yaydi → suratga oling → baho tayyor",
        actions = { IconButton(onClick = { m.loadOmr() }) { Icon(Icons.Default.Refresh, "Yangilash") } }) {
        t.omrLast?.let { r ->
            item {
                Panel {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(56.dp).clip(CircleShape).background(markColor(r.mark, x).copy(alpha = 0.18f)),
                            contentAlignment = Alignment.Center) { Text("${r.mark}", style = Numbers, color = markColor(r.mark, x)) }
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(r.student, style = MaterialTheme.typography.titleMedium)
                            Text("${r.right} / ${r.total} to‘g‘ri · ${r.percent}% · ${variantLetter(r.variant)} variant", style = MaterialTheme.typography.bodyMedium)
                            if (r.wrong.isNotEmpty()) Text("Xato: ${r.wrong.joinToString(", ")}", style = MaterialTheme.typography.bodySmall, color = x.muted)
                        }
                    }
                }
            }
        }
        item {
            Panel {
                Text("Yangi varaqa", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(title, { title = it }, label = { Text("Nomi (masalan: 7-B fizika, 1-chorak)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    OutlinedTextField(n, { n = it.filter(Char::isDigit).take(2) }, label = { Text("Savollar") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f))
                    OutlinedTextField(copies, { copies = it.filter(Char::isDigit).take(2) }, label = { Text("Nusxa soni") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f))
                }
                Spacer(Modifier.height(8.dp))
                Text("Variantlar", style = MaterialTheme.typography.labelLarge)
                ChipRow((1..4).map { it.toString() to "$it ta" }, variants.toString()) { variants = it.toInt() }
                OutlinedTextField(key, { key = it.uppercase().filter { c -> c in "ABCD" } }, label = { Text("To‘g‘ri javoblar (ixtiyoriy): ABCDA…") },
                    singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
                Text("${key.length} / ${n.toIntOrNull() ?: 0}", style = MaterialTheme.typography.labelSmall, color = x.muted)
                Button(onClick = { m.createSheet(title.ifBlank { "Test" }, n.toIntOrNull() ?: 20, variants, key, copies.toIntOrNull() ?: 1, false) },
                    enabled = (n.toIntOrNull() ?: 0) in 1..60 && (key.isEmpty() || key.length == n.toIntOrNull()),
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                    Icon(Icons.Default.Print, null); Spacer(Modifier.width(8.dp)); Text("Varaqa tayyorlash (kompyuterda chop etish)")
                }
                t.lastTest?.let { (q, v) ->
                    OutlinedButton(onClick = { m.createSheet(title.ifBlank { "Oxirgi test" }, q, v, "", copies.toIntOrNull() ?: 1, true) },
                        modifier = Modifier.fillMaxWidth()) { Text("Oxirgi tuzilgan test uchun ($q savol, $v variant, kalit bilan)") }
                }
            }
        }
        if (t.omrSets.isNotEmpty()) item { SectionTitle("Varaqalar") }
        items(t.omrSets, key = { it.id }) { s ->
            Panel {
                Text(s.title, style = MaterialTheme.typography.titleSmall)
                Text("${s.questions} savol · ${s.variants} variant · ${s.results.size} ta tekshirildi" +
                    if (s.keys.isEmpty()) " · kalit yo‘q" else "", style = MaterialTheme.typography.bodySmall, color = x.muted)
                OutlinedTextField(student, { student = it }, label = { Text("O‘quvchi (ixtiyoriy)") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                    Button(onClick = {
                        val who = student
                        m.onUploaded = { path -> m.gradeSheet(s, path, who) }
                        act.takePhoto(); student = ""
                    }, enabled = s.keys.isNotEmpty()) { Icon(Icons.Default.PhotoCamera, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Suratga olib tekshirish") }
                    TextButton(onClick = { keyFor = s }) { Text("Kalit") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { val who = student; m.onUploaded = { p -> m.gradeSheet(s, p, who) }; act.pickImage() },
                        enabled = s.keys.isNotEmpty()) { Text("Galereyadan") }
                    TextButton(onClick = { m.previewFile(s.pdf) }) { Text("Varaqani ko‘rish") }
                    IconButton(onClick = { act.saveResult(s.pdf) }) { Icon(Icons.Default.Download, "Telefonga yuklab olish") }
                }
                s.results.take(5).forEach { r ->
                    Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(r.student, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        Text("${r.right}/${r.total}", style = MaterialTheme.typography.bodySmall, color = x.muted)
                        Spacer(Modifier.width(10.dp))
                        Text("${r.mark}", fontWeight = FontWeight.Bold, color = markColor(r.mark, x))
                    }
                }
            }
        }
        item {
            Text("Burchakdagi 4 ta qora kvadrat suratga to‘liq tushsin. Natijalar kompyuterda Excel faylga yoziladi. " +
                "Hammasi kompyuterda tekshiriladi — internet va AI kerak emas.", style = MaterialTheme.typography.bodySmall, color = x.muted)
        }
    }
    keyFor?.let { s ->
        var v by remember { mutableStateOf(1) }
        var k by remember { mutableStateOf(s.keys["1"].orEmpty()) }
        AlertDialog(onDismissRequest = { keyFor = null }, title = { Text("To‘g‘ri javoblar") },
            text = {
                Column {
                    if (s.variants > 1) ChipRow((1..s.variants).map { it.toString() to "${variantLetter(it)} variant" }, v.toString()) {
                        v = it.toInt(); k = s.keys[it].orEmpty()
                    }
                    OutlinedTextField(k, { k = it.uppercase().filter { c -> c in "ABCD" } }, label = { Text("ABCD… (${s.questions} ta)") },
                        modifier = Modifier.fillMaxWidth())
                    Text("${k.length} / ${s.questions}", style = MaterialTheme.typography.labelSmall)
                }
            },
            confirmButton = { Button(onClick = { m.setOmrKey(s, v, k); keyFor = null }, enabled = k.length == s.questions) { Text("Saqlash") } },
            dismissButton = { TextButton(onClick = { keyFor = null }) { Text("Bekor qilish") } })
    }
}

// ---------------- class journal ----------------
@Composable
fun JournalScreen(m: AppModel) {
    val x = LocalExtra.current
    val t = m.tools
    LaunchedEffect(Unit) { m.loadJournal() }
    var adding by remember { mutableStateOf(false) }
    var addingStudents by remember { mutableStateOf(false) }
    var deleting by remember { mutableStateOf<JClass?>(null) }
    var subject by rememberSaveable { mutableStateOf("") }
    val v = t.jview
    if (v == null) {
        Screen(m, "Sinf jurnali", "Telefondan baho qo‘ying — Excel jurnal kompyuterda",
            actions = { IconButton(onClick = { adding = true }) { Icon(Icons.Default.Add, "Sinf qo‘shish") } }) {
            if (t.classes.isEmpty()) item { EmptyState(Icons.Default.Groups, "Sinf yo‘q", "+ tugmasi bilan sinf qo‘shing (masalan «7-B»).", "Sinf qo‘shish") { adding = true } }
            items(t.classes, key = { it.id }) { c ->
                Panel(onClick = { m.openClass(c.id, "") }) {
                    ListRow(Icons.Default.Groups, c.name, "${c.students} ta o‘quvchi", Brand.Indigo) {
                        IconButton(onClick = { deleting = c }) { Icon(Icons.Default.DeleteOutline, "O‘chirish", tint = x.danger) }
                    }
                }
            }
        }
    } else {
        Screen(m, v.name, "${v.students.size} ta o‘quvchi", actions = {
            IconButton(onClick = { addingStudents = true }) { Icon(Icons.Default.PersonAdd, "O‘quvchi qo‘shish") }
            IconButton(onClick = { m.exportJournal(v.id) }) { Icon(Icons.Default.TableChart, "Excel") }
        }) {
            item {
                OutlinedTextField(subject, { subject = it }, label = { Text("Fan (masalan: Fizika)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                if (v.subjects.isNotEmpty()) ChipRow(listOf("" to "Hammasi") + v.subjects.map { it to it }, t.jSubject) {
                    t.jSubject = it; if (it.isNotBlank()) subject = it; m.openClass(v.id, it)
                }
            }
            if (v.students.isEmpty()) item { EmptyState(Icons.Default.PersonAdd, "O‘quvchilar yo‘q", "Ro‘yxatni nusxalab joylashtiring — har qatorda bitta ism.", "Qo‘shish") { addingStudents = true } }
            items(v.students, key = { it.id }) { s ->
                Panel(padding = 12.dp) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(s.name, style = MaterialTheme.typography.titleSmall)
                            Text((s.grades.takeLast(6).joinToString(" ") { it.grade.toString() }).ifBlank { "baho yo‘q" } +
                                (s.average?.let { "  ·  o‘rtacha ${usFmt("%.1f", it)}" } ?: ""), style = MaterialTheme.typography.bodySmall, color = x.muted)
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(top = 6.dp)) {
                        (2..5).forEach { g ->
                            FilledTonalButton(onClick = { m.putGrade(s, g, subject.ifBlank { "Fan" }) }, enabled = subject.isNotBlank(),
                                contentPadding = PaddingValues(0.dp), modifier = Modifier.weight(1f).height(44.dp),
                                colors = ButtonDefaults.filledTonalButtonColors(containerColor = markColor(g, x).copy(alpha = 0.16f), contentColor = markColor(g, x))) {
                                Text("$g", style = MaterialTheme.typography.titleMedium)
                            }
                        }
                    }
                }
            }
            item {
                Text(if (subject.isBlank()) "Baho qo‘yish uchun avval fan nomini yozing." else "Baho bugungi sana bilan yoziladi. Excel jurnal: yuqoridagi jadval belgisi.",
                    style = MaterialTheme.typography.bodySmall, color = x.muted)
                TextButton(onClick = { t.jview = null; m.loadJournal() }) { Text("← Sinflar") }
            }
        }
    }
    if (adding) TextInputDialog("Yangi sinf", label = "Sinf nomi, masalan 7-B", onSave = { m.addClass(it) }, onDismiss = { adding = false })
    if (addingStudents && v != null) TextInputDialog("O‘quvchilar", label = "Har qatorda bitta ism-familiya", multiline = true,
        onSave = { m.addStudents(v.id, it) }, onDismiss = { addingStudents = false })
    deleting?.let { c -> ConfirmDialog("Sinfni o‘chirish", "«${c.name}» va undagi barcha baholar o‘chirilsinmi? Qaytarib bo‘lmaydi.",
        "O‘chirish", danger = true, onYes = { m.deleteClass(c.id) }, onDismiss = { deleting = null }) }
}

// ---------------- document templates ----------------
@Composable
fun DocumentsScreen(m: AppModel) {
    val x = LocalExtra.current
    LaunchedEffect(Unit) { m.loadTemplates() }
    var open by remember { mutableStateOf<DocTemplate?>(null) }
    Screen(m, "Hujjat shablonlari", "To‘ldiring — Word kompyuterda yozadi (DOCX + PDF)") {
        m.tools.templates.groupBy { it.group }.forEach { (group, list) ->
            item { SectionTitle(group) }
            items(list, key = { it.id }) { t ->
                Panel(onClick = { open = t }, padding = 12.dp) { ListRow(Icons.Default.Description, t.title, "${t.fields.size} ta maydon", Brand.Indigo) }
            }
        }
        if (m.tools.templates.isEmpty()) item { Text("Yuklanmoqda…", color = x.muted) }
    }
    open?.let { t ->
        val values = remember(t.id) { mutableStateMapOf<String, String>() }
        var bg by remember { mutableStateOf(false) }
        AlertDialog(onDismissRequest = { open = null }, title = { Text(t.title) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    t.fields.forEach { f ->
                        OutlinedTextField(values[f.key].orEmpty(), { values[f.key] = it }, label = { Text(f.label) },
                            placeholder = { Text(f.example) }, minLines = if (f.key in setOf("matn", "bandlar")) 3 else 1,
                            modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp))
                    }
                    TextButton(onClick = { t.fields.forEach { f -> if (values[f.key].isNullOrBlank()) values[f.key] = f.example } }) { Text("Namuna bilan to‘ldirish") }
                    Row(verticalAlignment = Alignment.CenterVertically) { Switch(bg, { bg = it }); Spacer(Modifier.width(8.dp)); Text("Fonda (Word ko‘rinmaydi)") }
                }
            },
            confirmButton = { Button(onClick = { m.makeDocument(t, values.toMap(), bg); open = null },
                enabled = t.fields.all { !values[it.key].isNullOrBlank() }) { Text("Yaratish") } },
            dismissButton = { TextButton(onClick = { open = null }) { Text("Bekor qilish") } })
    }
}

// ---------------- lesson schedule + reminders (on the phone) ----------------
@Composable
fun ScheduleScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val s = m.schedule
    var day by rememberSaveable { mutableStateOf(Schedule.todayIndex()) }
    var adding by remember { mutableStateOf(false) }
    Screen(m, "Dars jadvali", "Darsdan oldin eslatma keladi (internetsiz)",
        actions = { IconButton(onClick = { adding = true }) { Icon(Icons.Default.Add, "Dars qo‘shish") } }) {
        item { ChipRow(Schedule.DAYS.mapIndexed { i, d -> i.toString() to d.take(2) + if (i == Schedule.todayIndex()) " •" else "" }, day.toString()) { day = it.toInt() } }
        val list = s.lessons.filter { it.day == day }
        if (list.isEmpty()) item { EmptyState(Icons.Default.Event, "${Schedule.DAYS[day]}: dars yo‘q", "+ tugmasi bilan dars qo‘shing.") }
        items(list, key = { it.id }) { l ->
            Panel(padding = 12.dp) {
                ListRow(Icons.Default.Schedule, "${l.start}  ${l.title}", l.room.ifBlank { null }, Brand.Cyan) {
                    IconButton(onClick = { s.remove(l); act.reschedule() }) { Icon(Icons.Default.DeleteOutline, "O‘chirish", tint = x.danger) }
                }
            }
        }
        item {
            Panel {
                Text("Eslatma darsdan oldin", style = MaterialTheme.typography.titleSmall)
                ChipRow(listOf(0, 5, 10, 15).map { it.toString() to if (it == 0) "Darhol" else "$it daqiqa" }, s.remindMinutes.toString()) {
                    s.setRemind(it.toInt()); act.reschedule()
                }
            }
        }
    }
    if (adding) {
        var start by remember { mutableStateOf("08:00") }
        var title by remember { mutableStateOf("") }
        var room by remember { mutableStateOf("") }
        var err by remember { mutableStateOf<String?>(null) }
        AlertDialog(onDismissRequest = { adding = false }, title = { Text("${Schedule.DAYS[day]}: yangi dars") },
            text = {
                Column {
                    OutlinedTextField(start, { start = it }, label = { Text("Boshlanish (SS:DD)") }, singleLine = true)
                    OutlinedTextField(title, { title = it }, label = { Text("Dars: 7-B fizika") }, singleLine = true)
                    OutlinedTextField(room, { room = it }, label = { Text("Xona (ixtiyoriy)") }, singleLine = true)
                    err?.let { Text(it, color = x.danger, style = MaterialTheme.typography.bodySmall) }
                }
            },
            confirmButton = { Button(onClick = {
                err = runCatching { s.add(day, start, title, room) }.exceptionOrNull()?.message
                if (err == null) { adding = false; act.reschedule() }
            }) { Text("Qo‘shish") } },
            dismissButton = { TextButton(onClick = { adding = false }) { Text("Bekor qilish") } })
    }
}

@Composable
fun TodayCard(m: AppModel) {
    val today = m.schedule.today()
    if (today.isEmpty()) return
    val x = LocalExtra.current
    SectionTitle("Bugungi darslar", "Jadval") { m.open(Screen.Schedule) }
    Panel {
        today.forEach { l ->
            Row(Modifier.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(l.start, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary, modifier = Modifier.width(60.dp))
                Text(l.title, Modifier.weight(1f))
                if (l.room.isNotBlank()) Text(l.room, color = x.muted, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

// ---------------- meeting notes (live dictation on the phone) ----------------
@Composable
fun DictationScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val t = m.tools
    Screen(m, "Majlis yozuvi", if (t.dictating) "Tinglayapman…" else "Gapirilganini matnga aylantiradi") {
        item {
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(onClick = { if (t.dictating) act.stopDictation() else act.startDictation() },
                        colors = if (t.dictating) ButtonDefaults.buttonColors(containerColor = x.danger) else ButtonDefaults.buttonColors()) {
                        Icon(if (t.dictating) Icons.Default.Stop else Icons.Default.Mic, null); Spacer(Modifier.width(6.dp))
                        Text(if (t.dictating) "To‘xtatish" else "Yozishni boshlash")
                    }
                    Spacer(Modifier.width(10.dp))
                    if (t.dictating) Dot(x.danger, 12.dp)
                }
                ChipRow(listOf("uz-UZ" to "O‘zbekcha", "ru-RU" to "Ruscha", "en-US" to "Inglizcha"), m.voiceLang) { m.useVoiceLang(it) }
                Text("Telefon mikrofon yonida tursin. Matn telefonning o‘z ovoz xizmati bilan yoziladi (bepul); uzun pauzalarda ham davom etadi.",
                    style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(top = 6.dp))
            }
        }
        item {
            Panel {
                SelectionContainer { Text((t.dictation + if (t.partial.isNotBlank()) " ${t.partial}…" else "").ifBlank { "Hali hech narsa yozilmadi" },
                    style = MaterialTheme.typography.bodyLarge) }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { m.sendDictation(true) }, enabled = t.dictation.isNotBlank() && !t.dictating, modifier = Modifier.weight(1f)) { Text("Bayonnoma (AI)") }
                OutlinedButton(onClick = { m.sendDictation(false) }, enabled = t.dictation.isNotBlank() && !t.dictating, modifier = Modifier.weight(1f)) { Text("Kompyuterga matn") }
            }
            Row {
                TextButton(onClick = { m.polishDictation() }, enabled = t.dictation.isNotBlank() && !t.dictating) { Text("AI bilan tahrirlash") }
                TextButton(onClick = { act.copyText(t.dictation) }, enabled = t.dictation.isNotBlank()) { Text("Nusxa") }
                TextButton(onClick = { t.dictation = "" }, enabled = t.dictation.isNotBlank() && !t.dictating) { Text("Tozalash") }
            }
            Text("Bayonnoma AI orqali (pullik, avval narx so‘raladi); shaxsiy ma’lumotlar kompyuterda yashiriladi.",
                style = MaterialTheme.typography.bodySmall, color = x.muted)
        }
    }
}

// ---------------- preview: PDF pages, picture or text ----------------
@Composable
fun PreviewScreen(m: AppModel, act: PhoneActions) {
    val p = m.tools.preview
    Column(Modifier.fillMaxSize()) {
        ScreenHeader(p?.title ?: "Ko‘rish", onBack = { m.goBack() })
        when (p) {
            null -> Text("Fayl tanlanmagan", Modifier.padding(Gutter))
            is Preview.Image -> Image(p.bitmap.asImageBitmap(), p.title, Modifier.fillMaxWidth().padding(8.dp))
            is Preview.Text -> SelectionContainer {
                Text(p.text, Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(Gutter), style = MaterialTheme.typography.bodyMedium)
            }
            is Preview.Pdf -> PdfPages(p)
        }
    }
}

@Composable
private fun PdfPages(p: Preview.Pdf) {
    val pages = remember(p.file) {
        runCatching {
            PdfRenderer(ParcelFileDescriptor.open(p.file, ParcelFileDescriptor.MODE_READ_ONLY)).use { r ->
                (0 until minOf(r.pageCount, 40)).map { i ->
                    r.openPage(i).use { page ->
                        val w = 1080
                        val h = (w.toFloat() * page.height / page.width).toInt()
                        Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888).also {
                            it.eraseColor(android.graphics.Color.WHITE)
                            page.render(it, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                        }
                    }
                }
            }
        }.getOrDefault(emptyList())
    }
    if (pages.isEmpty()) { Text("PDF ochilmadi", Modifier.padding(Gutter)); return }
    LazyColumn(contentPadding = PaddingValues(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(pages) { b -> Image(b.asImageBitmap(), null, Modifier.fillMaxWidth().clip(MaterialTheme.shapes.small)) }
    }
}

// ---------------- photo → text (in Files) ----------------
@Composable
fun OcrPanel(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    var lang by rememberSaveable { mutableStateOf("") }
    Panel {
        Text("Rasmdan matn", style = MaterialTheme.typography.titleMedium)
        Text("Darslik sahifasi yoki hujjatni suratga oling — matn kompyuterda o‘qiladi (internetsiz).", style = MaterialTheme.typography.bodySmall, color = x.muted)
        ChipRow(listOf("" to "Avto", "uz" to "Lotin", "ru" to "Kirill"), lang) { lang = it }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
            Button(onClick = { val l = lang; m.onUploaded = { m.ocr(it, l) }; act.takePhoto() }, modifier = Modifier.weight(1f)) {
                Icon(Icons.Default.PhotoCamera, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Suratga olish")
            }
            OutlinedButton(onClick = { val l = lang; m.onUploaded = { m.ocr(it, l) }; act.pickImage() }, modifier = Modifier.weight(1f)) { Text("Galereyadan") }
        }
        TextButton(onClick = { m.onUploaded = { m.send("AI bilan shu rasmdagi matnni aniq o‘qi"); m.open(Screen.Chat) }; act.takePhoto() }) {
            Icon(Icons.Default.AutoAwesome, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Qo‘lyozma: AI bilan aniq o‘qish")
        }
        m.tools.ocrText?.let { text ->
            HorizontalDivider(Modifier.padding(vertical = 8.dp), color = x.cardBorder)
            SelectionContainer { Text(text.take(3000), style = MaterialTheme.typography.bodyMedium) }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                TextButton(onClick = { act.copyText(text) }) { Text("Nusxa") }
                TextButton(onClick = { m.compose("AI bilan shu matndan 10 ta test tuz: ${text.take(3000)}") }) { Text("Test (AI)") }
                TextButton(onClick = { m.compose("AI bilan shu matnni qisqa konspekt qil: ${text.take(3000)}") }) { Text("Konspekt (AI)") }
            }
        }
    }
}

// ---------------- scanner (in Files) ----------------
@Composable
fun ScanPanel(act: PhoneActions) {
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBadge(Icons.Default.DocumentScanner, Color(0xFF0EA5E9)); Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("Hujjatni skanerlash", style = MaterialTheme.typography.titleMedium)
                Text("Qog‘ozni suratga oling — chetlari o‘zi topiladi, tekislanadi va PDF bo‘lib kompyuterga boradi.",
                    style = MaterialTheme.typography.bodySmall, color = LocalExtra.current.muted)
            }
        }
        Button(onClick = act.scanDocument, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) { Text("Skanerlash → PDF") }
    }
}
