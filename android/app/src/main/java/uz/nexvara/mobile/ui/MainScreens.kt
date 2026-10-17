package uz.nexvara.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import uz.nexvara.mobile.*

/** What only the Activity can do (system pickers, camera, speech, browser, Google). */
class PhoneActions(
    val scanQr: () -> Unit, val pickFile: () -> Unit, val pickImage: () -> Unit, val pickPdf: () -> Unit,
    val takePhoto: () -> Unit, val listen: () -> Unit, val saveResult: (String) -> Unit,
    val openUrl: (String) -> Unit, val googleSignIn: (String) -> Unit, val stopSpeaking: () -> Unit,
    val unlock: () -> Unit,
)

private data class NavItem(val screen: Screen, val label: String, val icon: ImageVector)

private val NAV = listOf(
    NavItem(Screen.Home, "Bosh sahifa", Icons.Default.Home),
    NavItem(Screen.Chat, "Suhbat", Icons.AutoMirrored.Filled.Chat),
    NavItem(Screen.Tasks, "Vazifalar", Icons.AutoMirrored.Filled.ListAlt),
    NavItem(Screen.Sections, "Bo‘limlar", Icons.Default.GridView),
)

@Composable
fun AppRoot(m: AppModel, act: PhoneActions) {
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(m.notice) {
        m.notice?.let { snack.showSnackbar(it, withDismissAction = true); m.notice = null }
    }
    BackHandler(enabled = m.screen != Screen.Home || m.pairing) {
        if (m.pairing && m.profile != null) m.pairing = false else m.goBack()
    }
    if (m.locked) { LockScreen(act); return }
    m.preview?.let { bmp ->
        androidx.compose.ui.window.Dialog(onDismissRequest = { m.preview = null }) {
            Panel(padding = 8.dp) {
                androidx.compose.foundation.Image(bmp.asImageBitmap(), "Natija", Modifier.fillMaxWidth())
                TextButton(onClick = { m.preview = null }, modifier = Modifier.align(Alignment.End)) { Text("Yopish") }
            }
        }
    }
    val needPair = m.profile == null || m.pairing
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(snack) },
        bottomBar = {
            if (!needPair) NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
                val current = if (m.screen.ordinal > Screen.Sections.ordinal) Screen.Sections else m.screen
                NAV.forEach { item ->
                    NavigationBarItem(
                        selected = current == item.screen, onClick = { m.open(item.screen) },
                        icon = {
                            if (item.screen == Screen.Tasks && (m.overview?.running ?: 0) > 0)
                                BadgedBox(badge = { Badge { Text("${m.overview?.running}") } }) { Icon(item.icon, null) }
                            else Icon(item.icon, null)
                        },
                        label = { Text(item.label, maxLines = 1) },
                    )
                }
            }
        },
    ) { inset ->
        Column(Modifier.fillMaxSize().padding(inset).consumeWindowInsets(inset).imePadding()) {
            AnimatedVisibility(m.busy > 0) { LinearProgressIndicator(Modifier.fillMaxWidth().height(2.dp)) }
            if (needPair) PairScreen(m, act) else when (m.screen) {
                Screen.Home -> HomeScreen(m, act)
                Screen.Chat -> ChatScreen(m, act)
                Screen.Tasks -> TasksScreen(m, act)
                Screen.Sections -> SectionsScreen(m)
                Screen.Office -> OfficeScreen(m, act)
                Screen.Library -> LibraryScreen(m)
                Screen.Files -> FilesScreen(m, act)
                Screen.Bi -> BiScreen(m)
                Screen.Workflows -> WorkflowsScreen(m)
                Screen.Teach -> TeachScreen(m)
                Screen.Memory -> MemoryScreen(m)
                Screen.Ai -> AiScreen(m, act)
                Screen.Devices -> DevicesScreen(m, act)
                Screen.Settings -> SettingsScreen(m, act)
            }
        }
    }
}

// ---------------- app lock ----------------
@Composable
fun LockScreen(act: PhoneActions) {
    LaunchedEffect(Unit) { act.unlock() }
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Logo(72.dp)
        Spacer(Modifier.height(20.dp))
        Text("NEXVARA qulflangan", style = MaterialTheme.typography.headlineSmall)
        Text("Barmoq izi, yuz yoki telefon PIN-kodi bilan oching", color = LocalExtra.current.muted,
            style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(24.dp))
        Button(onClick = act.unlock, modifier = Modifier.height(52.dp)) {
            Icon(Icons.Default.Fingerprint, null); Spacer(Modifier.width(8.dp)); Text("Ochish")
        }
    }
}

// ---------------- pairing ----------------
@Composable
fun PairScreen(m: AppModel, act: PhoneActions) {
    var manual by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 20.dp)) {
        if (m.profile != null) TextButton(onClick = { m.pairing = false }) { Text("← Orqaga") }
        Spacer(Modifier.height(24.dp))
        Logo(64.dp)
        Spacer(Modifier.height(22.dp))
        Text("NEXVARA’ga xush kelibsiz", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("Telefoningizni Windows’dagi NEXVARA bilan bog‘lang. Keyin Excel, Word, PowerPoint, darsliklar va " +
            "AI’ni shu yerdan boshqarasiz — ish kompyuter ekranida jonli bajariladi.",
            style = MaterialTheme.typography.bodyLarge, color = LocalExtra.current.muted)
        Spacer(Modifier.height(26.dp))
        Panel {
            listOf(
                "Kompyuterda NEXVARA’ni oching" to Icons.Default.DesktopWindows,
                "«Qurilmalar» bo‘limida «Telefon ulanishini yoqish»" to Icons.Default.PhonelinkSetup,
                "Ekrandagi QR kodni skanerlang" to Icons.Default.QrCodeScanner,
            ).forEachIndexed { i, (t, ic) ->
                ListRow(ic, "${i + 1}. $t", tint = if (i == 2) Brand.Cyan else MaterialTheme.colorScheme.primary)
            }
        }
        Spacer(Modifier.height(20.dp))
        Button(onClick = act.scanQr, enabled = m.busy == 0, modifier = Modifier.fillMaxWidth().height(54.dp)) {
            Icon(Icons.Default.QrCodeScanner, null); Spacer(Modifier.width(10.dp)); Text("QR kodni skanerlash")
        }
        Spacer(Modifier.height(20.dp))
        Text("yoki havolani joylang", style = MaterialTheme.typography.labelLarge, color = LocalExtra.current.muted)
        Spacer(Modifier.height(6.dp))
        OutlinedTextField(manual, { manual = it }, placeholder = { Text("https://192.168…#p=…") },
            modifier = Modifier.fillMaxWidth(), singleLine = true)
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { m.connect(manual) }, enabled = manual.isNotBlank() && m.busy == 0, modifier = Modifier.fillMaxWidth()) {
            Text("Bog‘lash")
        }
        Spacer(Modifier.height(20.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Lock, null, tint = LocalExtra.current.success, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("Aloqa shifrlangan, faqat shu kompyuter sertifikati qabul qilinadi. Telefon va kompyuter bir Wi-Fi’da bo‘lsin.",
                style = MaterialTheme.typography.bodySmall, color = LocalExtra.current.muted)
        }
    }
}

// ---------------- home ----------------
@Composable
fun HomeScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val ov = m.overview
    val pcLabel = m.profile?.optString("label")?.ifBlank { null } ?: m.profile?.optString("pc") ?: "Kompyuter"
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(Gutter)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Logo(36.dp); Spacer(Modifier.width(10.dp))
                Text("NEXVARA", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                IconButton(onClick = { m.open(Screen.Settings) }) { Icon(Icons.Default.Settings, "Sozlamalar") }
            }
            Spacer(Modifier.height(12.dp))
            // Hero: the connected PC and the main actions.
            Box(Modifier.fillMaxWidth().clip(MaterialTheme.shapes.extraLarge)
                .background(Brush.linearGradient(listOf(Color(0xFF4F46E5), Color(0xFF6366F1), Color(0xFF0891B2))))
                .padding(20.dp)) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.DesktopWindows, null, tint = Color.White)
                        Spacer(Modifier.width(8.dp))
                        Text(pcLabel, color = Color.White, style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Row(Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.18f)).padding(horizontal = 10.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically) {
                            Dot(when (m.connected) { true -> Color(0xFF4ADE80); false -> Color(0xFFFCA5A5); null -> Color.White.copy(0.6f) })
                            Spacer(Modifier.width(6.dp))
                            Text(when (m.connected) { true -> "Ulangan"; false -> "Aloqa yo‘q"; null -> "Tekshirilmoqda" },
                                color = Color.White, style = MaterialTheme.typography.labelMedium)
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                    Text("Bugun nima qilamiz?", color = Color.White, style = MaterialTheme.typography.headlineSmall)
                    Text("Buyruq yozing yoki ayting — kompyuter ekranida bajariladi.", color = Color.White.copy(alpha = 0.85f),
                        style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(16.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(onClick = { m.open(Screen.Chat) }, colors = ButtonDefaults.buttonColors(containerColor = Color.White,
                            contentColor = Color(0xFF3730A3)), modifier = Modifier.weight(1f)) {
                            Icon(Icons.Default.Edit, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Yozish")
                        }
                        Button(onClick = { m.open(Screen.Chat); act.listen() }, colors = ButtonDefaults.buttonColors(
                            containerColor = Color.White.copy(alpha = 0.2f), contentColor = Color.White), modifier = Modifier.weight(1f)) {
                            Icon(Icons.Default.Mic, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Gapirish")
                        }
                    }
                }
            }
            if (m.queued > 0) {
                Spacer(Modifier.height(10.dp))
                Panel { ListRow(Icons.Default.CloudQueue, "${m.queued} ta buyruq navbatda", "Kompyuter bilan aloqa tiklanganda yuboriladi", x.warning) }
            }
            SectionTitle("Tezkor amallar")
            val quick = listOf(
                Triple(Icons.Default.TableChart, "Excel", Screen.Office), Triple(Icons.Default.School, "Test tuzish", Screen.Library),
                Triple(Icons.Default.Insights, "BI panellar", Screen.Bi), Triple(Icons.Default.UploadFile, "Fayl yuborish", Screen.Files),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                quick.forEachIndexed { i, (ic, t, s) ->
                    Column(Modifier.weight(1f).clip(MaterialTheme.shapes.large).background(x.card)
                        .clickableSafe { m.open(s) }.padding(vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        IconBadge(ic, listOf(Color(0xFF16A34A), Brand.Indigo, Brand.Cyan, Color(0xFFF59E0B))[i], 42.dp)
                        Spacer(Modifier.height(6.dp))
                        Text(t, style = MaterialTheme.typography.labelMedium, maxLines = 1)
                    }
                }
            }
            SectionTitle("AI balans va xarajatlar", "Batafsil") { m.open(Screen.Ai) }
            AiSummary(ov?.ai, onOpen = { m.open(Screen.Ai) })
            SectionTitle("Oxirgi vazifalar", "Hammasi") { m.open(Screen.Tasks) }
        }
        val recent = m.tasks.take(3)
        if (recent.isEmpty()) item { Panel { Text("Hali vazifa yo‘q. Suhbatda buyruq bering.", color = x.muted) } }
        items(recent, key = { "h" + it.id }) { TaskCard(m, it, act, compact = true); Spacer(Modifier.height(10.dp)) }
        item {
            SectionTitle("NEXVARA holati")
            Panel {
                val c = ov?.counts ?: emptyMap()
                Row(Modifier.fillMaxWidth()) {
                    Stat("Xotira", c["memory"], Modifier.weight(1f)) { m.open(Screen.Memory) }
                    Stat("Qoidalar", c["teach"], Modifier.weight(1f)) { m.open(Screen.Teach) }
                    Stat("Jarayonlar", c["workflows"], Modifier.weight(1f)) { m.open(Screen.Workflows) }
                    Stat("Panellar", c["dashboards"], Modifier.weight(1f)) { m.open(Screen.Bi) }
                }
                ov?.sync?.let { s ->
                    HorizontalDivider(Modifier.padding(vertical = 10.dp), color = x.cardBorder)
                    ListRow(Icons.Default.Sync, if (s.enabled && s.folderName.isNotBlank()) "Sinxron: ${s.folderName}" else "Sinxron sozlanmagan",
                        if (s.enabled) "Oxirgi: ${Fmt.ago(s.last)} · shifrlangan" else "Kompyuterda Sozlamalar → Sinxronlash", Brand.Cyan)
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Stat(label: String, value: Int?, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.clip(MaterialTheme.shapes.medium).clickableSafe(onClick).padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value?.toString() ?: "—", style = Numbers, color = MaterialTheme.colorScheme.primary)
        Text(label, style = MaterialTheme.typography.labelMedium, color = LocalExtra.current.muted, maxLines = 1)
    }
}

fun Modifier.clickableSafe(onClick: () -> Unit): Modifier = this.then(Modifier.clickable(onClick = onClick))

@Composable
fun AiSummary(ai: AiPanel?, onOpen: () -> Unit) {
    val x = LocalExtra.current
    Panel(onClick = onOpen) {
        if (ai == null) { Text("Yuklanmoqda…", color = x.muted); return@Panel }
        Row(verticalAlignment = Alignment.Bottom) {
            Column(Modifier.weight(1f)) {
                Text("Bu oy", style = MaterialTheme.typography.labelMedium, color = x.muted)
                Text(Fmt.usdFine(ai.spentMonth), style = Numbers)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("Bugun", style = MaterialTheme.typography.labelMedium, color = x.muted)
                Text(Fmt.usdFine(ai.spentToday), style = MaterialTheme.typography.titleMedium)
            }
        }
        Spacer(Modifier.height(8.dp))
        LimitBar(ai.spentMonth, ai.monthlyBudget)
        Text("Oylik limit ${Fmt.usd(ai.monthlyBudget)} · AI ${if (ai.enabled) "yoqilgan" else "o‘chiq"}",
            style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(top = 4.dp))
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ai.providers.forEach { p ->
                Column(Modifier.weight(1f).clip(MaterialTheme.shapes.medium).background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
                    .padding(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Dot(if (p.hasKey) x.success else x.muted, 7.dp); Spacer(Modifier.width(4.dp))
                        Text(shortName(p), style = MaterialTheme.typography.labelSmall, maxLines = 1)
                    }
                    Text(Fmt.usdFine(p.spentMonth), style = MaterialTheme.typography.titleSmall)
                    Text(if (p.leftMonth != null) "qoldi ${Fmt.usd(p.leftMonth)}" else "—", style = MaterialTheme.typography.labelSmall,
                        color = x.muted, maxLines = 1)
                }
            }
        }
        ai.warnings.forEach { Text("⚠ $it", color = x.warning, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp)) }
    }
}

fun shortName(p: AiProvider) = when (p.id) { "anthropic" -> "Claude"; "gemini" -> "Gemini"; "openai" -> "OpenAI"; "deepseek" -> "DeepSeek"; else -> p.label }

// ---------------- chat ----------------
@Composable
fun ChatScreen(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    var input by rememberSaveable { mutableStateOf("") }
    var bg by rememberSaveable { mutableStateOf(false) }
    var attach by remember { mutableStateOf(false) }
    LaunchedEffect(m.dictated) {
        m.dictated?.let { said ->
            m.dictated = null
            if (m.speakReplies) m.send(said, bg) else input = (input + " " + said).trim()
        }
    }
    val list = rememberLazyListState()
    LaunchedEffect(m.messages.size) { if (m.messages.isNotEmpty()) list.animateScrollToItem(m.messages.size - 1) }
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("AI suhbat", if (m.speakReplies) "Ovozli suhbat yoqilgan" else "Buyruqlar kompyuterda bajariladi") {
            IconButton(onClick = { m.setSpeak(!m.speakReplies); if (!m.speakReplies) act.stopSpeaking() }) {
                Icon(if (m.speakReplies) Icons.Default.RecordVoiceOver else Icons.Default.VoiceOverOff,
                    "Javoblarni ovoz bilan o‘qish", tint = if (m.speakReplies) MaterialTheme.colorScheme.primary else x.muted)
            }
        }
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = list, contentPadding = PaddingValues(horizontal = Gutter, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (m.messages.isEmpty()) item {
                Column {
                    EmptyState(Icons.Default.AutoAwesome, "Nima qilay?", "Masalan quyidagilardan birini tanlang yoki o‘zingiz yozing.")
                    listOf("Hisobot.xlsx ni och, jadvalni formatla va PDF qilib saqla", "7-sinf fizika 20 ta test 2 variant",
                        "Savdo dashboardini ko‘rsat", "Eslab qol: maktabim 21-maktab").forEach { s ->
                        SuggestionChip(onClick = { input = s }, label = { Text(s, maxLines = 2) }, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
            items(m.messages) { msg -> Bubble(msg) }
            m.confirm?.let { c ->
                item {
                    Panel {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Paid, null, tint = x.warning); Spacer(Modifier.width(8.dp))
                            Text("Tasdiq kerak", style = MaterialTheme.typography.titleSmall)
                        }
                        if (c.text.isNotBlank()) Text(c.text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp))
                        Spacer(Modifier.height(10.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Button(onClick = { m.answer(true) }, modifier = Modifier.weight(1f)) { Text("Ha, davom et") }
                            OutlinedButton(onClick = { m.answer(false) }, modifier = Modifier.weight(1f)) { Text("Yo‘q") }
                        }
                    }
                }
            }
        }
        // Composer
        Surface(color = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
            Column(Modifier.padding(horizontal = 10.dp, vertical = 8.dp)) {
                AnimatedVisibility(attach) {
                    Row(Modifier.fillMaxWidth().padding(bottom = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        AssistChip(onClick = { attach = false; act.pickFile() }, label = { Text("Fayl") }, leadingIcon = { Icon(Icons.Default.AttachFile, null) })
                        AssistChip(onClick = { attach = false; act.pickPdf() }, label = { Text("PDF") }, leadingIcon = { Icon(Icons.Default.PictureAsPdf, null) })
                        AssistChip(onClick = { attach = false; act.pickImage() }, label = { Text("Rasm") }, leadingIcon = { Icon(Icons.Default.Image, null) })
                        AssistChip(onClick = { attach = false; act.takePhoto() }, label = { Text("Kamera") }, leadingIcon = { Icon(Icons.Default.PhotoCamera, null) })
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    FilterChip(selected = bg, onClick = { bg = !bg }, label = { Text("Fonda bajar") },
                        leadingIcon = { Icon(if (bg) Icons.Default.VisibilityOff else Icons.Default.Visibility, null, Modifier.size(16.dp)) })
                    Spacer(Modifier.width(8.dp))
                    Text(if (bg) "Office oynasi ko‘rinmaydi" else "Office kompyuter ekranida ochiladi",
                        style = MaterialTheme.typography.labelSmall, color = x.muted)
                }
                Row(verticalAlignment = Alignment.Bottom) {
                    IconButton(onClick = { attach = !attach }) { Icon(if (attach) Icons.Default.Close else Icons.Default.Add, "Biriktirish") }
                    OutlinedTextField(input, { input = it }, modifier = Modifier.weight(1f), placeholder = { Text("Buyruq yozing…") },
                        maxLines = 5, shape = RoundedCornerShape(22.dp))
                    Spacer(Modifier.width(6.dp))
                    if (input.isBlank()) FilledIconButton(onClick = act.listen, modifier = Modifier.size(48.dp)) { Icon(Icons.Default.Mic, "Ovozli buyruq") }
                    else FilledIconButton(onClick = { m.send(input, bg); input = "" }, modifier = Modifier.size(48.dp)) {
                        Icon(Icons.AutoMirrored.Filled.Send, "Yuborish")
                    }
                }
            }
        }
    }
}

@Composable
private fun Bubble(msg: ChatMsg) {
    val mine = msg.mine
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
        Surface(
            color = if (mine) MaterialTheme.colorScheme.primary else LocalExtra.current.card,
            contentColor = if (mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
            shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp, bottomStart = if (mine) 20.dp else 6.dp, bottomEnd = if (mine) 6.dp else 20.dp),
            border = if (mine) null else androidx.compose.foundation.BorderStroke(1.dp, LocalExtra.current.cardBorder),
            modifier = Modifier.widthIn(max = 320.dp),
        ) { Text(msg.text, Modifier.padding(horizontal = 14.dp, vertical = 10.dp), style = MaterialTheme.typography.bodyLarge) }
    }
}

// ---------------- tasks ----------------
@Composable
fun TasksScreen(m: AppModel, act: PhoneActions) {
    var filter by rememberSaveable { mutableStateOf("all") }
    val shown = m.tasks.filter {
        when (filter) { "active" -> it.active; "done" -> it.status == "succeeded"; "failed" -> it.status in setOf("failed", "cancelled"); else -> true }
    }
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Vazifalar", "Kompyuterdagi jarayonlar jonli yangilanadi") {
            IconButton(onClick = { m.refreshTasks() }) { Icon(Icons.Default.Refresh, "Yangilash") }
        }
        Box(Modifier.padding(horizontal = Gutter)) {
            ChipRow(listOf("all" to "Hammasi", "active" to "Bajarilmoqda", "done" to "Tayyor", "failed" to "Xato/bekor"), filter) { filter = it }
        }
        LazyColumn(contentPadding = PaddingValues(Gutter), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (shown.isEmpty()) item { EmptyState(Icons.AutoMirrored.Filled.ListAlt, "Vazifa yo‘q", "Suhbatda buyruq bering — jarayon shu yerda ko‘rinadi.") }
            items(shown, key = { it.id }) { TaskCard(m, it, act) }
        }
    }
}

@Composable
fun TaskCard(m: AppModel, t: TaskItem, act: PhoneActions, compact: Boolean = false) {
    val x = LocalExtra.current
    var open by rememberSaveable(t.id) { mutableStateOf(t.active && !compact) }
    Panel(onClick = { open = !open }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(t.title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.width(8.dp))
            StatusPill(t.status, if (t.pauseRequested && t.status == "running") "Pauza kutilmoqda" else Fmt.status(t.status))
        }
        if (t.active && t.steps.isNotEmpty()) {
            val done = t.steps.count { it.status == "succeeded" }
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(progress = { (done.toFloat() / (t.steps.size + 1)).coerceIn(0.05f, 1f) },
                modifier = Modifier.fillMaxWidth().height(5.dp).clip(CircleShape), drawStopIndicator = {})
            Text(t.steps.last().name, style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(top = 4.dp))
        }
        if (t.error.isNotBlank()) Text(t.error, color = x.danger, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
        if (open && !compact) {
            Spacer(Modifier.height(8.dp))
            t.steps.forEach { s ->
                Row(Modifier.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(statusIcon(s.status), null, tint = statusColor(s.status, x), modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(s.name + if (s.detail.isNotBlank()) " — ${s.detail}" else "", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        if (t.files.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            t.files.forEach { f ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    AssistChip(onClick = { act.saveResult(f) }, label = { Text(TransferChecks.resultFileName(f), maxLines = 1) },
                        leadingIcon = { Icon(Icons.Default.Download, null, Modifier.size(18.dp)) }, modifier = Modifier.weight(1f, fill = false))
                    if (f.lowercase().let { it.endsWith(".png") || it.endsWith(".jpg") || it.endsWith(".jpeg") }) {
                        Spacer(Modifier.width(6.dp))
                        AssistChip(onClick = { m.previewImage(f) }, label = { Text("Ko‘rish") },
                            leadingIcon = { Icon(Icons.Default.Visibility, null, Modifier.size(18.dp)) })
                    }
                }
            }
        }
        if (t.active) {
            Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (t.status == "paused" || t.pauseRequested)
                    FilledTonalButton(onClick = { m.resumeTask(t) }) { Icon(Icons.Default.PlayArrow, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Davom ettirish") }
                else OutlinedButton(onClick = { m.pauseTask(t) }, enabled = !t.cancelRequested) {
                    Icon(Icons.Default.Pause, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Pauza")
                }
                TextButton(onClick = { m.cancelTask(t) }, enabled = !t.cancelRequested,
                    colors = ButtonDefaults.textButtonColors(contentColor = x.danger)) { Text(if (t.cancelRequested) "To‘xtatilmoqda…" else "Bekor qilish") }
            }
        }
    }
}

// ---------------- sections grid (the 12 sections of the Windows app) ----------------
@Composable
fun SectionsScreen(m: AppModel) {
    val c = m.overview?.counts ?: emptyMap()
    val items = listOf(
        Triple(Screen.Office, Icons.Default.Description, "Excel, Word, PowerPoint, chizma"),
        Triple(Screen.Library, Icons.Default.School, "Darslikdan test tuzish"),
        Triple(Screen.Files, Icons.Default.Folder, "Yuborish va natijalar"),
        Triple(Screen.Bi, Icons.Default.Insights, "${c["dashboards"] ?: 0} ta panel"),
        Triple(Screen.Workflows, Icons.Default.AccountTree, "${c["workflows"] ?: 0} ta jarayon"),
        Triple(Screen.Teach, Icons.Default.Psychology, "${c["teach"] ?: 0} ta qoida"),
        Triple(Screen.Memory, Icons.Default.Bookmarks, "${c["memory"] ?: 0} ta eslatma"),
        Triple(Screen.Ai, Icons.Default.AccountBalanceWallet, "Balans va limitlar"),
        Triple(Screen.Devices, Icons.Default.Devices, "Ish va uy kompyuteri"),
        Triple(Screen.Settings, Icons.Default.Settings, "Mavzu, ovoz, Google"),
    )
    val tints = listOf(Color(0xFF16A34A), Brand.Indigo, Color(0xFFF59E0B), Brand.Cyan, Color(0xFF8B5CF6),
        Color(0xFFEC4899), Color(0xFF0EA5E9), Color(0xFF10B981), Color(0xFF64748B), Color(0xFF6366F1))
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Bo‘limlar", "Windows NEXVARA’ning barcha bo‘limlari")
        LazyVerticalGrid(GridCells.Fixed(2), contentPadding = PaddingValues(Gutter), horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(items.indices.toList()) { i ->
                val (s, ic, sub) = items[i]
                Tile(ic, s.title, sub, tints[i]) { m.open(s) }
            }
        }
    }
}
