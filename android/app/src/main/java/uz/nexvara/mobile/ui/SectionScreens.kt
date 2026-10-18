package uz.nexvara.mobile.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import uz.nexvara.mobile.*

private val Green = Color(0xFF16A34A)
private val Blue = Color(0xFF2563EB)
private val Orange = Color(0xFFEA580C)
private val CHART = listOf(Color(0xFF6366F1), Color(0xFF06B6D4), Color(0xFFF59E0B), Color(0xFF10B981), Color(0xFFEC4899), Color(0xFF8B5CF6))

@Composable
private fun SubScreen(m: AppModel, title: String, subtitle: String? = null, actions: @Composable RowScope.() -> Unit = {},
                      content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit) {
    Column(Modifier.fillMaxSize()) {
        ScreenHeader(title, subtitle, onBack = { m.goBack() }, actions = actions)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = Gutter, end = Gutter, bottom = 28.dp, top = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

// ---------------- Office ----------------
@Composable
fun OfficeScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    var cmd by rememberSaveable { mutableStateOf("") }
    var bg by rememberSaveable { mutableStateOf(false) }
    var draw by rememberSaveable { mutableStateOf("") }
    SubScreen(m, "Office yordamchisi", "Excel, Word, PowerPoint kompyuter ekranida jonli") {
        item {
            Panel {
                Text("Buyruq bering", style = MaterialTheme.typography.titleMedium)
                Text("Fayl nomini yozing yoki avval Fayllar bo‘limidan yuboring («shu fayl»).", style = MaterialTheme.typography.bodySmall, color = x.muted)
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(cmd, { cmd = it }, modifier = Modifier.fillMaxWidth(), minLines = 2,
                    placeholder = { Text("Hisobot.xlsx ni och, dublikatlarni o‘chir, jami qo‘sh, PDF qilib saqla") })
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
                    Switch(bg, { bg = it }); Spacer(Modifier.width(8.dp))
                    Text(if (bg) "Fonda (oyna ko‘rinmaydi)" else "Ekranda ko‘rinib bajariladi", style = MaterialTheme.typography.bodyMedium)
                }
                Spacer(Modifier.height(8.dp))
                Button(onClick = { m.send(cmd, bg); cmd = ""; m.open(Screen.Chat) }, enabled = cmd.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.PlayArrow, null); Spacer(Modifier.width(6.dp)); Text("Bajarish")
                }
            }
        }
        item {
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBadge(Icons.Default.Architecture, Color(0xFF8B5CF6)); Spacer(Modifier.width(12.dp))
                    Column {
                        Text("Chizma", style = MaterialTheme.typography.titleMedium)
                        Text("Aytganingizni chizadi yoki qo‘lda chizilgan eskizni toza chizmaga aylantiradi",
                            style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(draw, { draw = it }, modifier = Modifier.fillMaxWidth(), minLines = 2,
                    placeholder = { Text("Masalan: diametri 80 mm flanes, markazda 30 mm teshik, 4 ta boltli teshik") })
                Spacer(Modifier.height(8.dp))
                Button(onClick = { m.send("$draw — shu chizmani chizib ber"); draw = ""; m.open(Screen.Chat) },
                    enabled = draw.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Draw, null); Spacer(Modifier.width(6.dp)); Text("Chizib berish")
                }
                Spacer(Modifier.height(8.dp))
                val fromPhoto = "Shu rasmdagi qo‘lda chizilgan chizmani mukammal chizib ber" + if (draw.isNotBlank()) ": $draw" else ""
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { m.afterUpload = fromPhoto; act.takePhoto() }, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Default.PhotoCamera, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Suratga olish")
                    }
                    OutlinedButton(onClick = { m.afterUpload = fromPhoto; act.pickImage() }, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Default.Image, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Galereyadan")
                    }
                }
                Text("AI kerak (OpenAI, Gemini yoki Claude). Narx va rasm yuborilishi avval so‘raladi; rasmdan joylashuv ma’lumoti o‘chiriladi. " +
                    "Natija: PDF kompyuter ekranida, PNG telefonda.", style = MaterialTheme.typography.bodySmall, color = x.muted,
                    modifier = Modifier.padding(top = 6.dp))
            }
        }
        item { SectionTitle("Tayyor namunalar (kompyuterda ochiladi)") }
        val ready = listOf(
            Triple("excel_demo", "Excel jadval", Icons.Default.TableChart) to Green,
            Triple("excel_dashboard", "Excel dashboard", Icons.Default.Dashboard) to Green,
            Triple("word_report", "Word hisobot", Icons.Default.Article) to Blue,
            Triple("presentation", "PowerPoint taqdimot", Icons.Default.Slideshow) to Orange,
        )
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                ready.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        row.forEach { (t, tint) -> Tile(t.third, t.second, "Bir bosishda", tint, Modifier.weight(1f)) { m.office(t.first) } }
                    }
                }
            }
        }
        item { SectionTitle("Namuna buyruqlar") }
        val samples = listOf(
            "Excel" to "Hisobot.xlsx ni och, jadvalni formatla, jami qo‘sh, diagramma qo‘sh",
            "Excel" to "Savdo.xlsx ni summa bo‘yicha kamayish tartibida sartirovka qil",
            "Word" to "Xat.docx ni och, sahifa raqamini qo‘y, PDF qilib saqla",
            "PowerPoint" to "Hisobot.pptx ga «Natijalar» slaydini qo‘sh",
        )
        items(samples) { (app, s) ->
            Panel(onClick = { cmd = s }, padding = 12.dp) {
                Text(app, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                Text(s, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

// ---------------- Textbooks and tests ----------------
@Composable
fun LibraryScreen(m: AppModel) {
    val x = LocalExtra.current
    val lib = m.library
    var grade by rememberSaveable { mutableStateOf<Int?>(null) }
    var subject by rememberSaveable { mutableStateOf<String?>(null) }
    var topic by rememberSaveable { mutableStateOf("") }
    var count by rememberSaveable { mutableStateOf(20f) }
    var variants by rememberSaveable { mutableStateOf(1) }
    var useAi by rememberSaveable { mutableStateOf(false) }
    SubScreen(m, "Darsliklar va testlar", lib?.let { "${it.books.size} ta darslik kompyuterda" }) {
        item {
            Panel {
                Text("Sinf", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(6.dp))
                val grades = lib?.catalog?.keys?.toList()?.ifEmpty { null } ?: (1..11).toList()
                ChipRow(grades.map { it.toString() to "$it-sinf" }, grade?.toString() ?: "") { grade = it.toInt(); subject = null }
                Spacer(Modifier.height(12.dp))
                Text("Fan", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(6.dp))
                val subjects = grade?.let { lib?.catalog?.get(it) }.orEmpty()
                if (subjects.isEmpty()) Text(if (grade == null) "Avval sinfni tanlang" else "Bu sinf uchun darslik topilmadi",
                    color = x.muted, style = MaterialTheme.typography.bodySmall)
                else ChipRow(subjects.map { it to it }, subject ?: "") { subject = it }
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(topic, { topic = it }, label = { Text("Mavzu (ixtiyoriy)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(12.dp))
                Text("Savollar soni: ${count.toInt()}", style = MaterialTheme.typography.titleSmall)
                Slider(count, { count = it }, valueRange = 5f..50f, steps = 8)
                Text("Variantlar", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(6.dp))
                ChipRow((1..4).map { it.toString() to "$it ta" }, variants.toString()) { variants = it.toInt() }
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Switch(useAi, { useAi = it }); Spacer(Modifier.width(8.dp))
                    Column {
                        Text("AI yordamida", style = MaterialTheme.typography.bodyLarge)
                        Text("Pullik — avval narx so‘raladi. O‘chiq bo‘lsa bepul, darslik matnidan.", style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                }
                Spacer(Modifier.height(14.dp))
                Button(onClick = { m.makeTest(grade, subject, topic, count.toInt(), variants, useAi) }, enabled = grade != null && subject != null,
                    modifier = Modifier.fillMaxWidth().height(50.dp)) {
                    Icon(Icons.Default.Quiz, null); Spacer(Modifier.width(8.dp)); Text("Test tuzish (Word kompyuterda)")
                }
                val what = listOfNotNull(grade?.let { "$it-sinf" }, subject, topic.ifBlank { null }).joinToString(" ")
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { m.send("$what mavzusini chiqarib ber"); m.open(Screen.Chat) },
                        enabled = grade != null && subject != null && topic.isNotBlank(), modifier = Modifier.weight(1f)) { Text("Mavzu matni") }
                    OutlinedButton(onClick = { m.send("$what bo‘yicha taqdimot tayyorla"); m.open(Screen.Chat) },
                        enabled = grade != null && subject != null && topic.isNotBlank(), modifier = Modifier.weight(1f)) { Text("Taqdimot") }
                }
                TextButton(onClick = { m.compose("AI bilan $what uchun 45 daqiqalik dars rejasi tuz") },
                    enabled = grade != null && subject != null) { Text("Dars rejasi (AI) →") }
            }
        }
        if (lib != null && lib.books.isNotEmpty()) {
            item { SectionTitle("Darsliklar") }
            items(lib.books.filter { grade == null || it.grade == grade }.take(60)) { b ->
                Panel(padding = 12.dp) { ListRow(Icons.Default.MenuBook, b.label, "${b.grade}-sinf · ${b.subject} · ${b.pages} bet", Brand.Indigo) }
            }
        } else if (lib != null) item {
            EmptyState(Icons.Default.MenuBook, "Darslik yo‘q", "Kompyuterda «Darsliklar va testlar» bo‘limida darsliklarni yuklang.")
        }
    }
}

// ---------------- Files ----------------
@Composable
fun FilesScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    SubScreen(m, "Fayllar", "Kompyuterga yuborish va natijalarni olish") {
        item {
            Panel {
                Text("Kompyuterga yuborish", style = MaterialTheme.typography.titleMedium)
                Text("Fayl kompyuterdagi «Telefondan» papkasiga tushadi va suhbatda «shu fayl» bo‘ladi.",
                    style = MaterialTheme.typography.bodySmall, color = x.muted)
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Tile(Icons.Default.AttachFile, "Fayl", null, Brand.Indigo, Modifier.weight(1f), act.pickFile)
                    Tile(Icons.Default.PictureAsPdf, "PDF", null, Color(0xFFDC2626), Modifier.weight(1f), act.pickPdf)
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Tile(Icons.Default.Image, "Rasm", null, Brand.Cyan, Modifier.weight(1f), act.pickImage)
                    Tile(Icons.Default.PhotoCamera, "Kamera", null, Color(0xFFF59E0B), Modifier.weight(1f), act.takePhoto)
                }
                m.lastUpload?.let {
                    Spacer(Modifier.height(10.dp))
                    ListRow(Icons.Default.CheckCircle, "Oxirgi yuborilgan: ${TransferChecks.resultFileName(it)}", "Endi suhbatda nima qilishni yozing", x.success,
                        onClick = { m.open(Screen.Chat) })
                }
            }
        }
        item { ScanPanel(act) }
        item { OcrPanel(m, act) }
        item { PcFilesPanel(m, act) }
        item { SectionTitle("Tayyor natijalar") }
        val results = m.results
        if (results.isEmpty()) item { EmptyState(Icons.Default.Inventory2, "Hali natija yo‘q", "NEXVARA yaratgan fayllar shu yerda paydo bo‘ladi.") }
        items(results.take(50)) { (t, f) ->
            Panel(padding = 12.dp) {
                ListRow(Icons.Default.InsertDriveFile, TransferChecks.resultFileName(f), t.title, Brand.Indigo, onClick = { m.previewFile(f) }) {
                    IconButton(onClick = { m.previewFile(f) }) { Icon(Icons.Default.Visibility, "Ko‘rish") }
                    IconButton(onClick = { act.saveResult(f) }) { Icon(Icons.Default.Download, "Yuklab olish") }
                }
            }
        }
        item {
            Text("Har bir fayl SHA-256 bilan tekshiriladi; buzilgan fayl saqlanmaydi.", style = MaterialTheme.typography.bodySmall, color = x.muted)
        }
    }
}

// ---------------- NEXVARA BI ----------------
@Composable
fun BiScreen(m: AppModel) {
    val v = m.biView
    if (v != null) return BiView(m, v)
    var onPc by rememberSaveable { mutableStateOf(true) }
    SubScreen(m, "NEXVARA BI", "Saqlangan panellar", actions = { IconButton(onClick = { m.loadBi() }) { Icon(Icons.Default.Refresh, "Yangilash") } }) {
        item {
            Panel(padding = 12.dp) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Switch(onPc, { onPc = it }); Spacer(Modifier.width(8.dp))
                    Text("Kompyuter ekranida ham ochish", style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
        if (m.dashboards.isEmpty()) item {
            EmptyState(Icons.Default.Insights, "Panel yo‘q", "Kompyuterda NEXVARA BI’da panel yarating yoki suhbatda «Savdo.xlsx dan dashboard qil» deng.",
                "Suhbatda yaratish") { m.open(Screen.Chat) }
        }
        items(m.dashboards) { d ->
            Panel(onClick = { m.openBi(d, onPc = onPc) }) {
                ListRow(Icons.Default.Insights, d.name, listOf(d.sourceName, "saqlangan ${Fmt.ago(d.saved)}").filter { it.isNotBlank() }.joinToString(" · "), Brand.Cyan) {
                    Icon(Icons.Default.ChevronRight, null)
                }
            }
        }
        item {
            SectionTitle("Chat orqali boshqarish")
            Panel {
                Text("«Savdo panelida faqat Toshkent», «yangi sahifa qo‘sh», «PDF qilib eksport qil» kabi buyruqlarni suhbatda yozing.",
                    style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { m.open(Screen.Chat) }) { Text("Suhbatga o‘tish") }
            }
        }
    }
}

@Composable
private fun BiView(m: AppModel, v: BiView) {
    val d = m.dashboards.firstOrNull { it.file == v.file }
    SubScreen(m, v.name, "${v.rows} / ${v.totalRows} qator",
        actions = { if (d != null) IconButton(onClick = { m.openBi(d, v.page) }) { Icon(Icons.Default.DesktopWindows, "Kompyuterda ochish") } }) {
        if (v.pages.size > 1 && d != null) item {
            ChipRow(v.pages.mapIndexed { i, p -> i.toString() to p }, v.page.toString()) { m.openBi(d, it.toInt(), onPc = false) }
        }
        val kpis = v.widgets.filter { it.type == "kpi" }
        if (kpis.isNotEmpty()) item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                kpis.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        row.forEach { w -> Kpi(w, Modifier.weight(1f)) }
                        if (row.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
            }
        }
        items(v.widgets.filter { it.type != "kpi" }) { w -> Chart(w) }
        v.problems.forEach { p -> item { Text("⚠ $p", color = LocalExtra.current.warning, style = MaterialTheme.typography.bodySmall) } }
    }
}

@Composable
private fun Kpi(w: Widget, modifier: Modifier) {
    val x = LocalExtra.current
    Panel(modifier, padding = 14.dp) {
        Text(w.title, style = MaterialTheme.typography.labelMedium, color = x.muted, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Text(Fmt.number(w.value) + if (w.unit.isNotBlank()) " ${w.unit}" else "", style = Numbers, maxLines = 1)
        w.growth?.let { g ->
            Text((if (g >= 0) "▲ " else "▼ ") + "%.1f%%".format(kotlin.math.abs(g)), color = if (g >= 0) x.success else x.danger,
                style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Composable
private fun Chart(w: Widget) {
    val x = LocalExtra.current
    Panel {
        Text(w.title.ifBlank { "Grafik" }, style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(10.dp))
        when (w.type) {
            "bar", "pie" -> {
                val max = w.values.filterNotNull().maxOrNull()?.takeIf { it > 0 } ?: 1.0
                val total = w.values.filterNotNull().sum().takeIf { it > 0 } ?: 1.0
                w.labels.zip(w.values).forEachIndexed { i, (label, value) ->
                    Column(Modifier.padding(vertical = 4.dp)) {
                        Row {
                            Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(Fmt.number(value) + if (w.type == "pie") "  (${"%.0f".format((value ?: 0.0) / total * 100)}%)" else "",
                                style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                        }
                        Spacer(Modifier.height(3.dp))
                        Box(Modifier.fillMaxWidth().height(10.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant)) {
                            Box(Modifier.fillMaxWidth(((value ?: 0.0) / max).toFloat().coerceIn(0.01f, 1f)).fillMaxHeight().clip(CircleShape)
                                .background(CHART[i % CHART.size]))
                        }
                    }
                }
            }
            "line" -> LineChart(w)
            "table" -> {
                Row { w.columns.take(3).forEach { Text(it, Modifier.weight(1f), style = MaterialTheme.typography.labelMedium, color = x.muted, maxLines = 1) } }
                HorizontalDivider(Modifier.padding(vertical = 4.dp), color = x.cardBorder)
                w.rows.take(12).forEach { r ->
                    Row(Modifier.padding(vertical = 3.dp)) { r.take(3).forEach { Text(it, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis) } }
                }
                if (w.rows.size > 12) Text("… yana ${w.rows.size - 12} qator (to‘liq jadval kompyuterda)", style = MaterialTheme.typography.bodySmall, color = x.muted)
            }
            else -> Text("Bu grafik turi kompyuter ekranida to‘liq ko‘rinadi.", color = x.muted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun LineChart(w: Widget) {
    val x = LocalExtra.current
    val all = w.series.flatMap { it.values }.filterNotNull()
    if (all.isEmpty()) { Text("Ma’lumot yo‘q", color = x.muted); return }
    val lo = minOf(0.0, all.min()); val hi = all.max().takeIf { it > lo } ?: (lo + 1)
    val grid = x.cardBorder
    Canvas(Modifier.fillMaxWidth().height(170.dp)) {
        for (i in 0..3) { val y = size.height * i / 3f; drawLine(grid, Offset(0f, y), Offset(size.width, y), 1f) }
        w.series.forEachIndexed { si, s ->
            val n = s.values.size
            if (n < 2) return@forEachIndexed
            val path = Path()
            var started = false
            s.values.forEachIndexed { i, v ->
                if (v == null) return@forEachIndexed
                val px = size.width * i / (n - 1)
                val py = size.height - ((v - lo) / (hi - lo)).toFloat() * size.height
                if (!started) { path.moveTo(px, py); started = true } else path.lineTo(px, py)
            }
            drawPath(path, CHART[si % CHART.size], style = Stroke(width = 5f, cap = StrokeCap.Round))
        }
    }
    Row(Modifier.fillMaxWidth().padding(top = 4.dp)) {
        Text(w.labels.firstOrNull().orEmpty(), style = MaterialTheme.typography.labelSmall, color = x.muted, modifier = Modifier.weight(1f))
        Text(w.labels.lastOrNull().orEmpty(), style = MaterialTheme.typography.labelSmall, color = x.muted)
    }
    if (w.series.size > 1) Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        w.series.forEachIndexed { i, s -> Row(verticalAlignment = Alignment.CenterVertically) { Dot(CHART[i % CHART.size]); Spacer(Modifier.width(4.dp)); Text(s.name, style = MaterialTheme.typography.labelSmall) } }
    }
}

// ---------------- Workflows ----------------
@Composable
fun WorkflowsScreen(m: AppModel) {
    val x = LocalExtra.current
    var creating by remember { mutableStateOf<JSONObject?>(null) }
    var deleting by remember { mutableStateOf<Workflow?>(null) }
    SubScreen(m, "Ish jarayonlari", "Bir necha qadamni avtomatik bajarish",
        actions = { IconButton(onClick = { creating = JSONObject().put("name", "").put("steps", JSONArray()).put("trigger", JSONObject().put("type", "manual")) }) {
            Icon(Icons.Default.Add, "Yangi jarayon") } }) {
        if (m.wfActive.isNotEmpty()) {
            item { SectionTitle("Hozir bajarilmoqda") }
            items(m.wfActive) { a ->
                Panel {
                    Text(a.name, style = MaterialTheme.typography.titleSmall)
                    Text(when { a.waitingApproval -> "Tasdiq kutmoqda"; a.paused -> "Pauzada"; else -> "Bajarilmoqda" }, color = x.info,
                        style = MaterialTheme.typography.bodySmall)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                        if (a.waitingApproval) Button(onClick = { m.runAction(a, "approve") }) { Text("Tasdiqlash") }
                        if (a.paused) FilledTonalButton(onClick = { m.runAction(a, "resume") }) { Text("Davom ettirish") }
                        else OutlinedButton(onClick = { m.runAction(a, "pause") }) { Text("Pauza") }
                    }
                }
            }
        }
        item { SectionTitle("Jarayonlar") }
        if (m.workflows.isEmpty()) item { EmptyState(Icons.Default.AccountTree, "Jarayon yo‘q", "Pastdagi shablondan boshlang yoki + tugmasini bosing.") }
        items(m.workflows) { w ->
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBadge(Icons.Default.AccountTree, Color(0xFF8B5CF6))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(w.name, style = MaterialTheme.typography.titleSmall)
                        Text(when (w.trigger) { "daily" -> "Har kuni ${w.time}"; "weekly" -> "Har hafta ${w.time}"; "folder" -> "Papkaga fayl tushganda"; else -> "Qo‘lda" } +
                            " · ${w.steps.size} qadam" + if (w.lastStatus.isNotBlank()) " · oxirgi: ${Fmt.status(w.lastStatus)}" else "",
                            style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                }
                w.steps.take(4).forEachIndexed { i, s ->
                    Text("${i + 1}. " + when (s.kind) { "approve" -> "✋ ${s.text.ifBlank { "Tasdiq" }}"; "wait" -> "⏱ ${s.seconds} soniya kutish"; else -> s.text },
                        style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    Button(onClick = { m.runWorkflow(w) }) { Icon(Icons.Default.PlayArrow, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Ishga tushirish") }
                    OutlinedButton(onClick = { creating = w.raw }) { Text("Tahrirlash") }
                    IconButton(onClick = { deleting = w }) { Icon(Icons.Default.DeleteOutline, "O‘chirish", tint = x.danger) }
                }
            }
        }
        if (m.wfTemplates.isNotEmpty()) {
            item { SectionTitle("Shablonlar") }
            items(m.wfTemplates) { t ->
                Panel(onClick = { creating = JSONObject(t.toString()) }, padding = 12.dp) {
                    ListRow(Icons.Default.AutoAwesome, t.optString("name"), "Bosing — tahrirlab saqlang", Brand.Indigo)
                }
            }
        }
    }
    creating?.let { wf -> WorkflowEditor(wf, onSave = { m.saveWorkflow(it) { creating = null } }, onDismiss = { creating = null }) }
    deleting?.let { w -> ConfirmDialog("Jarayonni o‘chirish", "«${w.name}» o‘chirilsinmi? Bu amalni qaytarib bo‘lmaydi.", "O‘chirish", danger = true,
        onYes = { m.deleteWorkflow(w) }, onDismiss = { deleting = null }) }
}

@Composable
private fun WorkflowEditor(initial: JSONObject, onSave: (JSONObject) -> Unit, onDismiss: () -> Unit) {
    var name by remember { mutableStateOf(initial.optString("name")) }
    val stepsArr = initial.optJSONArray("steps") ?: JSONArray()
    var steps by remember {
        mutableStateOf((0 until stepsArr.length()).joinToString("\n") { i ->
            val s = stepsArr.getJSONObject(i)
            when (s.optString("kind")) { "approve" -> "tasdiq: " + s.optString("text"); "wait" -> "kut: " + s.optInt("seconds"); else -> s.optString("text") }
        })
    }
    val trig = initial.optJSONObject("trigger") ?: JSONObject().put("type", "manual")
    var type by remember { mutableStateOf(trig.optString("type", "manual")) }
    var time by remember { mutableStateOf(trig.optString("time").ifBlank { "08:00" }) }
    var days by remember { mutableStateOf(trig.optJSONArray("days")?.let { a -> (0 until a.length()).map { a.optInt(it) }.toSet() } ?: setOf(0)) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(if (initial.optInt("id") > 0) "Jarayonni tahrirlash" else "Yangi jarayon") },
        text = {
            Column(Modifier.verticalScrollSafe()) {
                OutlinedTextField(name, { name = it }, label = { Text("Nomi") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(steps, { steps = it }, label = { Text("Qadamlar (har qatorda bitta buyruq)") }, minLines = 4, modifier = Modifier.fillMaxWidth())
                Text("«tasdiq: …» — sizdan so‘raydi, «kut: 30» — 30 soniya kutadi.", style = MaterialTheme.typography.bodySmall, color = LocalExtra.current.muted)
                Spacer(Modifier.height(8.dp))
                val opts = mutableListOf("manual" to "Qo‘lda", "daily" to "Har kuni", "weekly" to "Hafta kunlari")
                if (type == "folder") opts += "folder" to "Papka"
                ChipRow(opts, type) { type = it }
                if (type == "weekly") ChipRow(listOf("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya").mapIndexed { i, d -> i.toString() to (if (i in days) "✓ " else "") + d }, "") { k ->
                    val i = k.toInt(); days = if (i in days) days - i else days + i
                }
                if (type == "daily" || type == "weekly") OutlinedTextField(time, { time = it }, label = { Text("Vaqt (SS:DD)") }, singleLine = true)
                if (type == "folder") Text("Papka kuzatuvi kompyuterda sozlanadi: ${trig.optString("folder").ifBlank { "tanlanmagan" }}",
                    style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            Button(onClick = {
                val arr = JSONArray()
                steps.lines().map { it.trim() }.filter { it.isNotEmpty() }.forEach { line ->
                    arr.put(when {
                        line.startsWith("tasdiq:", true) -> JSONObject().put("kind", "approve").put("text", line.substringAfter(':').trim())
                        line.startsWith("kut:", true) -> JSONObject().put("kind", "wait").put("seconds", line.substringAfter(':').trim().toIntOrNull() ?: 10)
                        else -> JSONObject().put("kind", "command").put("text", line)
                    })
                }
                val t = JSONObject(trig.toString()).put("type", type)
                if (type == "daily" || type == "weekly") t.put("time", time.trim())
                if (type == "weekly") t.put("days", JSONArray(days.sorted()))
                onSave(JSONObject(initial.toString()).put("name", name.trim()).put("steps", arr).put("trigger", t))
            }, enabled = name.isNotBlank() && steps.isNotBlank()) { Text("Saqlash") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Bekor qilish") } })
}

@Composable
private fun Modifier.verticalScrollSafe() = this.then(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()))

// ---------------- Teach NEXVARA ----------------
@Composable
fun TeachScreen(m: AppModel) {
    val x = LocalExtra.current
    var app by rememberSaveable { mutableStateOf("excel") }
    var text by rememberSaveable { mutableStateOf("") }
    var preview by remember { mutableStateOf<Pair<Boolean, String>?>(null) }
    var deleting by remember { mutableStateOf<Rule?>(null) }
    SubScreen(m, "NEXVARA’ga o‘rgatish", "Sizning odatlaringiz — har buyruqqa qo‘shiladi") {
        item {
            Panel {
                Text("Yangi qoida", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                ChipRow(m.ruleApps.toList(), app) { app = it; preview = null }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(text, { text = it; preview = null }, modifier = Modifier.fillMaxWidth(), minLines = 2,
                    placeholder = { Text(when (app) { "test" -> "2 variant, 25 ta savol"; "word" -> "sahifa raqamini qo‘y"; "powerpoint" -> "PDF qilib saqla"; else -> "jadvalni formatla va jami qo‘sh" }) })
                preview?.let { (ok, info) ->
                    Text(info, color = if (ok) x.success else x.danger, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    OutlinedButton(onClick = { m.previewRule(app, text) { ok, info -> preview = ok to info } }, enabled = text.isNotBlank()) { Text("Tekshirish") }
                    Button(onClick = { m.addRule(app, text); text = ""; preview = null }, enabled = preview?.first == true) { Text("Saqlash") }
                }
                Text("Avval tekshiring: NEXVARA qoidani qanday tushunganini ko‘rsatadi.", style = MaterialTheme.typography.bodySmall, color = x.muted,
                    modifier = Modifier.padding(top = 4.dp))
            }
        }
        if (m.rules.isEmpty()) item { EmptyState(Icons.Default.Psychology, "Qoida yo‘q", "Masalan Excel uchun: «jadvalni formatla va jami qo‘sh», Word uchun: «sahifa raqamini qo‘y», testlar uchun: «2 variant, 25 ta savol».") }
        items(m.rules) { r ->
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(r.appLabel, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, modifier = Modifier.weight(1f))
                    Text("v${r.version}", style = MaterialTheme.typography.labelSmall, color = x.muted)
                    Spacer(Modifier.width(8.dp))
                    Switch(r.enabled, { m.toggleRule(r, it) })
                }
                Text(r.text, style = MaterialTheme.typography.bodyLarge)
                r.actions.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall, color = x.muted) }
                if (r.problem.isNotBlank()) Text(r.problem, color = x.danger, style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = { deleting = r }, colors = ButtonDefaults.textButtonColors(contentColor = x.danger)) { Text("O‘chirish") }
            }
        }
    }
    deleting?.let { r -> ConfirmDialog("Qoidani o‘chirish", "«${r.text}» o‘chirilsinmi?", "O‘chirish", danger = true,
        onYes = { m.deleteRule(r) }, onDismiss = { deleting = null }) }
}

// ---------------- Memory ----------------
@Composable
fun MemoryScreen(m: AppModel) {
    val x = LocalExtra.current
    var adding by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<Fact?>(null) }
    var deleting by remember { mutableStateOf<Fact?>(null) }
    var query by rememberSaveable { mutableStateOf("") }
    var found by remember { mutableStateOf<List<String>?>(null) }
    SubScreen(m, "Xotira", "NEXVARA eslab qolgan narsalar", actions = { IconButton(onClick = { adding = true }) { Icon(Icons.Default.Add, "Qo‘shish") } }) {
        item {
            OutlinedTextField(query, { query = it; if (it.isBlank()) found = null }, modifier = Modifier.fillMaxWidth(), singleLine = true,
                placeholder = { Text("Xotiradan qidirish…") }, leadingIcon = { Icon(Icons.Default.Search, null) },
                trailingIcon = { if (query.isNotBlank()) IconButton(onClick = { m.searchMemory(query) { found = it } }) { Icon(Icons.Default.ArrowForward, "Qidirish") } })
        }
        found?.let { f ->
            item { SectionTitle("Topildi: ${f.size}") }
            items(f) { Panel(padding = 12.dp) { Text(it, style = MaterialTheme.typography.bodyMedium, maxLines = 4, overflow = TextOverflow.Ellipsis) } }
        }
        item { SectionTitle("Eslatmalar") }
        if (m.facts.isEmpty()) item { EmptyState(Icons.Default.Bookmarks, "Hali eslatma yo‘q", "Suhbatda «Eslab qol: …» deb yozing yoki + tugmasini bosing.") }
        items(m.facts, key = { it.id }) { f ->
            Panel(padding = 12.dp) {
                Text(f.text, style = MaterialTheme.typography.bodyLarge)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(Fmt.ago(f.updated), style = MaterialTheme.typography.labelSmall, color = x.muted, modifier = Modifier.weight(1f))
                    IconButton(onClick = { editing = f }) { Icon(Icons.Default.Edit, "Tahrirlash", Modifier.size(20.dp)) }
                    IconButton(onClick = { deleting = f }) { Icon(Icons.Default.DeleteOutline, "O‘chirish", Modifier.size(20.dp), tint = x.danger) }
                }
            }
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
                Icon(Icons.Default.Sync, null, tint = x.muted, modifier = Modifier.size(16.dp)); Spacer(Modifier.width(6.dp))
                Text("Xotira kompyuterda saqlanadi va NEXVARA-SYNC orqali shifrlangan holda sinxronlanadi.",
                    style = MaterialTheme.typography.bodySmall, color = x.muted)
            }
        }
    }
    if (adding) TextInputDialog("Eslab qolish", label = "Matn", multiline = true, onSave = { m.addFact(it) }, onDismiss = { adding = false })
    editing?.let { f -> TextInputDialog("Tahrirlash", f.text, "Matn", multiline = true, onSave = { m.editFact(f, it) }, onDismiss = { editing = null }) }
    deleting?.let { f -> ConfirmDialog("Eslatmani o‘chirish", "«${f.text.take(80)}» o‘chirilsinmi?", "O‘chirish", danger = true,
        onYes = { m.deleteFact(f) }, onDismiss = { deleting = null }) }
}

// ---------------- AI balance and spend ----------------
@Composable
fun AiScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    // fresh numbers every time it opens, and again once the PC connection is up (cold start)
    LaunchedEffect(m.connected) { m.loadAi(); m.loadAiDirections() }
    val ai = m.ai ?: m.overview?.ai
    SubScreen(m, "AI balans va xarajatlar", "Windows va telefon birgalikda (bitta hisob)",
        actions = { IconButton(onClick = { m.loadAi() }) { Icon(Icons.Default.Refresh, "Yangilash") } }) {
        if (ai == null) { item { Text("Yuklanmoqda…", color = x.muted) }; return@SubScreen }
        item {
            Panel {
                Row {
                    Column(Modifier.weight(1f)) {
                        Text("Bugun", style = MaterialTheme.typography.labelMedium, color = x.muted)
                        Text(Fmt.usdFine(ai.spentToday), style = Numbers)
                        Text("limit ${Fmt.usd(ai.dailyBudget)}", style = MaterialTheme.typography.labelSmall, color = x.muted)
                    }
                    Column(Modifier.weight(1f)) {
                        Text("Bu oy", style = MaterialTheme.typography.labelMedium, color = x.muted)
                        Text(Fmt.usdFine(ai.spentMonth), style = Numbers)
                        Text("limit ${Fmt.usd(ai.monthlyBudget)}", style = MaterialTheme.typography.labelSmall, color = x.muted)
                    }
                }
                Spacer(Modifier.height(10.dp)); LimitBar(ai.spentMonth, ai.monthlyBudget)
                Spacer(Modifier.height(8.dp))
                Text(if (ai.enabled) "AI yoqilgan" else "AI o‘chiq — pullik so‘rov yuborilmaydi", color = if (ai.enabled) x.success else x.muted,
                    style = MaterialTheme.typography.bodySmall)
                ai.warnings.forEach { Text("⚠ $it", color = x.warning, style = MaterialTheme.typography.bodySmall) }
            }
        }
        item { AiDirectionsPanel(m) }
        items(ai.providers) { p ->
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBadge(Icons.Default.AutoAwesome, providerTint(p.id))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(p.label, style = MaterialTheme.typography.titleSmall)
                        Text(if (p.hasKey) "Ulangan" else "Kalit kiritilmagan", style = MaterialTheme.typography.bodySmall,
                            color = if (p.hasKey) x.success else x.muted)
                    }
                    Text(Fmt.usdFine(p.spentMonth), style = MaterialTheme.typography.titleMedium)
                }
                Spacer(Modifier.height(10.dp))
                Row {
                    Column(Modifier.weight(1f)) {
                        Text("Bugun: ${Fmt.usdFine(p.spentToday)}", style = MaterialTheme.typography.bodySmall)
                        Text("Kunlik limitdan qoldi: ${Fmt.usd(p.leftToday)}", style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Column(Modifier.weight(1f)) {
                        Text("Oylik limit: ${Fmt.usd(p.monthlyLimit)}", style = MaterialTheme.typography.bodySmall)
                        Text("Qoldi: ${Fmt.usd(p.leftMonth)}", style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                }
                Spacer(Modifier.height(6.dp)); LimitBar(p.spentMonth, p.monthlyLimit)
                Spacer(Modifier.height(8.dp))
                Text(when {
                    p.balance != null -> "Haqiqiy balans: ${p.balance}"
                    p.balanceApi -> "Haqiqiy balans: yangilash tugmasini bosing"
                    else -> "Haqiqiy balans: provayder rasmiy API bermaydi — billing sahifasida ko‘ring"
                }, style = MaterialTheme.typography.bodySmall, color = if (p.balance != null) MaterialTheme.colorScheme.onSurface else x.muted)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    if (p.billingUrl.isNotBlank()) FilledTonalButton(onClick = { act.openUrl(p.billingUrl) }) {
                        Icon(Icons.Default.Payments, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("To‘ldirish")
                    }
                    if (p.usageUrl.isNotBlank() && p.usageUrl != p.billingUrl) OutlinedButton(onClick = { act.openUrl(p.usageUrl) }) {
                        Icon(Icons.AutoMirrored.Filled.OpenInNew, null, Modifier.size(16.dp)); Spacer(Modifier.width(4.dp)); Text("Sarf")
                    }
                    if (p.balanceApi && p.hasKey) IconButton(onClick = { m.refreshBalance(p) }) { Icon(Icons.Default.Refresh, "Balansni yangilash") }
                }
            }
        }
        item {
            Text("To‘lov rasmiy sahifada, brauzerda bo‘ladi. NEXVARA karta ma’lumotini so‘ramaydi va saqlamaydi. Sarf NEXVARA hisob-kitobi " +
                "(taxminiy); limitlar NEXVARA’ning o‘z limitlari, provayderdagi haqiqiy chegara emas. Kalitlar faqat kompyuterning himoyalangan xotirasida.",
                style = MaterialTheme.typography.bodySmall, color = x.muted)
        }
        if (ai.history.isNotEmpty()) {
            item { SectionTitle("Oxirgi so‘rovlar") }
            items(ai.history.take(15)) { h ->
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Text(h.purpose.ifBlank { h.provider }, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                    Text(h.provider, style = MaterialTheme.typography.bodySmall, color = x.muted)
                    Spacer(Modifier.width(10.dp))
                    Text(Fmt.usdFine(h.cost), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

private fun providerTint(id: String) = when (id) {
    "openai" -> Color(0xFF10A37F); "gemini" -> Color(0xFF4285F4); "anthropic" -> Color(0xFFD97757); else -> Color(0xFF4D6BFE)
}

// ---------------- PCs (work / home) and Google ----------------
@Composable
fun DevicesScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    var renaming by remember { mutableStateOf<JSONObject?>(null) }
    var leaving by remember { mutableStateOf(false) }
    val activeSid = m.profile?.optString("sid")
    SubScreen(m, "Kompyuterlar", "Ish va uy kompyuterini tanlang") {
        items(m.pcs) { pc ->
            val active = pc.optString("sid") == activeSid
            Panel(onClick = if (active) null else ({ m.selectPc(pc.optString("sid")) })) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBadge(Icons.Default.DesktopWindows, if (active) MaterialTheme.colorScheme.primary else x.muted)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(pc.optString("label").ifBlank { pc.optString("pc", "Windows kompyuter") }, style = MaterialTheme.typography.titleSmall)
                        Text(if (active) (if (m.connected == true) "Tanlangan · ulangan" else "Tanlangan · aloqa yo‘q") else "Tanlash uchun bosing",
                            style = MaterialTheme.typography.bodySmall, color = if (active && m.connected == true) x.success else x.muted)
                    }
                    IconButton(onClick = { renaming = pc }) { Icon(Icons.Default.Edit, "Nomini o‘zgartirish") }
                }
            }
        }
        if (m.canWake) item {
            FilledTonalButton(onClick = { m.wakePc() }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.PowerSettingsNew, null); Spacer(Modifier.width(6.dp)); Text("Tanlangan kompyuterni yoqish")
            }
        }
        item {
            OutlinedButton(onClick = { m.pairing = true }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("Yana kompyuter qo‘shish")
            }
        }
        item {
            TextButton(onClick = { leaving = true }, colors = ButtonDefaults.textButtonColors(contentColor = x.danger)) { Text("Tanlangan kompyuterdan chiqish") }
        }
        item { SectionTitle("Google hisobi") }
        item { GoogleCard(m, act) }
    }
    renaming?.let { pc -> TextInputDialog("Kompyuter nomi", pc.optString("label").ifBlank { pc.optString("pc") }, "Masalan: Ish kompyuteri",
        onSave = { m.renamePc(pc.optString("sid"), it) }, onDismiss = { renaming = null }) }
    if (leaving) ConfirmDialog("Kompyuterdan chiqish", "Bu telefon tanlangan kompyuterdan uziladi. Qayta ulanish uchun QR kod kerak bo‘ladi.",
        "Chiqish", danger = true, onYes = { m.logoutPc() }, onDismiss = { leaving = false })
}

@Composable
fun GoogleCard(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val a = m.overview?.account
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBadge(Icons.Default.AccountCircle, Color(0xFF4285F4))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(when {
                    a == null -> "Yuklanmoqda…"
                    a.linkedEmail.isNotBlank() -> "Bog‘langan: ${a.linkedEmail}"
                    a.pcSignedIn -> "Kompyuterda: ${a.pcEmail}"
                    else -> "Kompyuterda Google bilan kirilmagan"
                }, style = MaterialTheme.typography.titleSmall)
                Text("Telefon faqat kompyuter egasining Google hisobi bilan bog‘lanadi.", style = MaterialTheme.typography.bodySmall, color = x.muted)
            }
        }
        Spacer(Modifier.height(10.dp))
        when {
            a == null -> Unit
            a.linkedEmail.isNotBlank() -> Text("✓ Telefon va kompyuter bitta hisobda", color = x.success)
            !a.ownerSet -> Text("Avval kompyuterda Sozlamalar → Google hisobi orqali kiring va «Ha, bu mening hisobim» deng.",
                style = MaterialTheme.typography.bodySmall)
            a.webClientId.isBlank() -> Text("Telefon uchun Google hali sozlanmagan: Google Cloud’da Android va Web OAuth client kerak " +
                "(docs/GOOGLE_LOGIN.md → Android). Parol yoki maxfiy kalit kerak emas.", style = MaterialTheme.typography.bodySmall, color = x.warning)
            else -> Button(onClick = { act.googleSignIn(a.webClientId) }, modifier = Modifier.fillMaxWidth()) { Text("Google bilan bog‘lash") }
        }
    }
}

// ---------------- Settings ----------------
@Composable
fun SettingsScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val ov = m.overview
    SubScreen(m, "Sozlamalar") {
        item { SectionTitle("Ko‘rinish") }
        item {
            Panel {
                Text("Mavzu", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                ChipRow(listOf("System" to "Tizim bo‘yicha", "Light" to "Yorug‘", "Dark" to "Qorong‘i"), m.themeMode.name) { m.setTheme(ThemeMode.valueOf(it)) }
                Spacer(Modifier.height(10.dp))
                Text("Til", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                ChipRow(listOf("uz" to "O‘zbek tili", "ru" to "Русский язык"), if (m.russian) "ru" else "uz") { m.useRussian(it == "ru") }
            }
        }
        item { SectionTitle("Xavfsizlik va ovoz") }
        item {
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Ilova qulfi", style = MaterialTheme.typography.bodyLarge)
                        Text("Ochishda barmoq izi, yuz yoki telefon PIN-kodi. 1 daqiqa fonda turgach yana qulflanadi.",
                            style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Switch(m.lockEnabled, { m.setLock(it) })
                }
                HorizontalDivider(Modifier.padding(vertical = 10.dp), color = x.cardBorder)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Ovozli suhbat", style = MaterialTheme.typography.bodyLarge)
                        Text("Aytilgan buyruq darhol yuboriladi, javob ovoz bilan o‘qiladi. Bepul, telefonning o‘z ovoz xizmati.",
                            style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Switch(m.speakReplies, { m.setSpeak(it); if (!it) act.stopSpeaking() })
                }
                HorizontalDivider(Modifier.padding(vertical = 10.dp), color = x.cardBorder)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("AI ovozi", style = MaterialTheme.typography.bodyLarge)
                        Text("Javobni kompyuterdagi AI o‘qiydi (o‘zbekcha tabiiyroq). Gemini bepul; pullik bo‘lsa narxi aytilib so‘raladi.",
                            style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Switch(m.aiVoice, { m.useAiVoice(it) })
                }
            }
        }
        item { SectionTitle("Ovoz tili") }
        item {
            Panel {
                Text("Gapirganda qaysi tilda tanisin", style = MaterialTheme.typography.bodyLarge)
                ChipRow(listOf("uz-UZ" to "O‘zbekcha", "ru-RU" to "Ruscha", "en-US" to "Inglizcha"), m.voiceLang) { m.useVoiceLang(it) }
                Text("O‘zbekcha tanish internet orqali (Google ovoz xizmati) ishlaydi.", style = MaterialTheme.typography.bodySmall, color = x.muted)
            }
        }
        item { SectionTitle("Kompyuter") }
        item {
            LaunchedEffect(Unit) { m.loadAutostart() }
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Windows bilan birga ishga tushsin", style = MaterialTheme.typography.bodyLarge)
                        Text("Kompyuter yoqilganda NEXVARA o‘zi ochiladi va telefon ulanadi", style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Switch(m.tools.autostart == true, { m.setAutostart(it) }, enabled = m.tools.autostart != null)
                }
                if (m.canWake) TextButton(onClick = { m.wakePc() }) { Text("Kompyuterni uyg‘otish (Wake-on-LAN)") }
            }
        }
        item { SectionTitle("Boshqa tarmoqdan ulanish") }
        item { NetworkCard(m, act) }
        item { SectionTitle("Maxfiylik va xabarlar") }
        item {
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Ekran rasmini taqiqlash", style = MaterialTheme.typography.bodyLarge)
                        Text("Skrinshot olinmaydi, «so‘nggi ilovalar»da ko‘rinmaydi", style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Switch(m.secureScreen, { m.useSecureScreen(it) })
                }
                HorizontalDivider(Modifier.padding(vertical = 10.dp), color = x.cardBorder)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Ilova yopiq bo‘lsa ham xabar", style = MaterialTheme.typography.bodyLarge)
                        Text("Har 15 daqiqada vazifalar tekshiriladi (kompyuter yoqiq bo‘lsa)", style = MaterialTheme.typography.bodySmall, color = x.muted)
                    }
                    Switch(m.backgroundAlerts, { m.useBackgroundAlerts(it) })
                }
                HorizontalDivider(Modifier.padding(vertical = 10.dp), color = x.cardBorder)
                MorningSettings()
            }
        }
        item { SectionTitle("Sinxronlash (NEXVARA-SYNC)") }
        item {
            Panel {
                val s = ov?.sync
                ListRow(Icons.Default.Sync, when {
                    s == null -> "Yuklanmoqda…"
                    s.enabled && s.folderName.isNotBlank() -> "Papka: ${s.folderName}"
                    else -> "Sinxronlash sozlanmagan"
                }, s?.let { "Oxirgi: ${Fmt.ago(it.last)} · parol ${if (it.hasPassphrase) "kompyuter himoyalangan xotirasida" else "o‘rnatilmagan"}" }, Brand.Cyan)
                Text("Xotira va Teach qoidalari kompyuter orqali OneDrive’dagi NEXVARA-SYNC papkasiga AES-GCM bilan shifrlangan holda yoziladi. " +
                    "Telefon parolni ko‘rmaydi va saqlamaydi.", style = MaterialTheme.typography.bodySmall, color = x.muted)
                TextButton(onClick = { m.send("sinxronla"); m.open(Screen.Chat) }, enabled = s?.enabled == true) { Text("Hozir sinxronlash") }
            }
        }
        item { SectionTitle("Google") }
        item { GoogleCard(m, act) }
        item { SectionTitle("Xavfsizlik") }
        item {
            Panel {
                ListRow(Icons.Default.Lock, "Shifrlangan aloqa", "Faqat QR’dagi sertifikat izi (SHA-256) qabul qilinadi", x.success)
                ListRow(Icons.Default.Key, "Token Android Keystore’da", "Chat tarixi va navbat ham shifrlangan", x.success)
                ListRow(Icons.Default.Shield, "Shaxsiy ma’lumotlar himoyasi", "AI’ga ketadigan har so‘rov kompyuterda yashiriladi", x.success)
            }
        }
        item {
            Text("NEXVARA Android ${BuildConfigInfo.version} · Kompyuter: ${ov?.version ?: "—"}", style = MaterialTheme.typography.bodySmall,
                color = x.muted, modifier = Modifier.padding(top = 12.dp))
        }
    }
}

object BuildConfigInfo { var version = "" }


/** «Ertalabki xulosa»: on/off, the time, and a button to see it now. */
@Composable
fun MorningSettings() {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val x = LocalExtra.current
    var on by remember { mutableStateOf(uz.nexvara.mobile.Morning.enabled(ctx)) }
    var time by remember { mutableStateOf(uz.nexvara.mobile.Morning.time(ctx)) }
    var error by remember { mutableStateOf<String?>(null) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Ertalabki xulosa", style = MaterialTheme.typography.bodyLarge)
            Text("Har kuni: bugungi darslar va kompyuterda kutayotgan ishlar", style = MaterialTheme.typography.bodySmall, color = x.muted)
        }
        Switch(on, { on = it; runCatching { uz.nexvara.mobile.Morning.set(ctx, it, time) } })
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(time, { v ->
            time = v.take(5)
            error = runCatching { uz.nexvara.mobile.Morning.set(ctx, on, time) }.exceptionOrNull()?.message
        }, label = { Text("Vaqt (HH:MM)") }, singleLine = true, isError = error != null, modifier = Modifier.weight(1f))
        TextButton(onClick = { Thread { uz.nexvara.mobile.Morning.show(ctx) }.start() }) { Text("Hozir ko‘rsat") }
    }
    error?.let { Text(it, color = x.danger, style = MaterialTheme.typography.bodySmall) }
    // Without the notification permission Android drops every NEXVARA notification silently.
    var allowed by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        while (true) {
            allowed = androidx.core.app.NotificationManagerCompat.from(ctx).areNotificationsEnabled()
            kotlinx.coroutines.delay(1500)
        }
    }
    if (!allowed) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Bildirishnomalar o‘chiq: ertalabki xulosa va «Tayyor» xabarlari kelmaydi",
                color = x.warning, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
            TextButton(onClick = {
                ctx.startActivity(android.content.Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, ctx.packageName)
                    .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
            }) { Text("Ruxsat berish") }
        }
    }
}


/** 🧠 AUTO or a chosen model per direction — the same settings as the PC (shared). */
@Composable
fun AiDirectionsPanel(m: AppModel) {
    val x = LocalExtra.current
    LaunchedEffect(Unit) { m.loadAiDirections() }
    Panel {
        Text("🧠 AI modeli: AUTO yoki qo‘lda", style = MaterialTheme.typography.titleMedium)
        Text("AUTO — avval bepul, keyin eng arzon mos model. Qo‘lda tanlangan model almashtirilmaydi. Kompyuter bilan bir xil sozlama.",
            style = MaterialTheme.typography.bodySmall, color = x.muted)
        if (m.aiv.directions.isEmpty()) Text("Yuklanmoqda…", color = x.muted)
        m.aiv.directions.forEach { d ->
            HorizontalDivider(Modifier.padding(vertical = 8.dp), color = x.cardBorder)
            Text(d.label, style = MaterialTheme.typography.bodyLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                FilterChip(selected = d.mode == "auto", onClick = { m.setAiDirection(d.id, "auto") }, label = { Text("AUTO") })
                FilterChip(selected = d.mode == "manual", onClick = {
                    val o = d.offers.firstOrNull { it.connected && it.models.isNotEmpty() }
                    if (o != null) m.setAiDirection(d.id, "manual", o.provider, o.models.first())
                    else m.notice = "Bu yo‘nalish uchun ulangan AI yo‘q (kompyuterda Sozlamalar → AI)"
                }, label = { Text("Qo‘lda") })
            }
            if (d.mode == "manual") {
                val connected = d.offers.filter { it.connected }
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    connected.forEach { o ->
                        FilterChip(selected = o.provider == d.provider, onClick = {
                            o.models.firstOrNull()?.let { m.setAiDirection(d.id, "manual", o.provider, it) }
                        }, label = { Text(o.label) })
                    }
                }
                connected.firstOrNull { it.provider == d.provider }?.let { o ->
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        o.models.forEach { mod ->
                            FilterChip(selected = mod == d.model, onClick = { m.setAiDirection(d.id, "manual", o.provider, mod) },
                                label = { Text(mod) })
                        }
                    }
                }
            } else if (d.autoPick.isNotBlank()) {
                Text("AUTO hozir: ${d.autoPick}", style = MaterialTheme.typography.bodySmall, color = x.muted)
            }
        }
    }
}
