package uz.nexvara.mobile

import android.os.Bundle
import android.provider.OpenableColumns
import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import org.json.JSONObject
import java.util.UUID

private val Indigo = Color(0xFF6366F1)
private val Cyan = Color(0xFF06B6D4)
private val Dark = Color(0xFF0B1020)
private data class Message(val text: String, val mine: Boolean)
private data class StepView(val name: String, val status: String, val detail: String)
private data class TaskView(val id: String, val title: String, val status: String, val error: String,
    val files: List<String>, val steps: List<StepView>)

class MainActivity : ComponentActivity() {
    private lateinit var secure: SecureSession
    private var profile by mutableStateOf<JSONObject?>(null)
    private var pairing by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var connected by mutableStateOf(false)
    private var notice by mutableStateOf("")
    private var tab by mutableStateOf(0)
    private val messages = mutableStateListOf<Message>()
    private val tasks = mutableStateListOf<TaskView>()
    private var pendingDownload by mutableStateOf<String?>(null)
    private var confirmToken by mutableStateOf<String?>(null)
    private var flushing by mutableStateOf(false)
    private var watchActive = false
    private var taskEtag = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        secure = SecureSession(this)
        profile = secure.read()
        loadHistory()
        setContent { NexvaraUi() }
        if (profile != null) refresh()
    }

    override fun onStart() {
        super.onStart()
        watchActive = true
        Thread {
            while (watchActive) {
                val current = profile
                if (current == null || pairing) { Thread.sleep(2_000); continue }
                try {
                    val path = "/api/v1/tasks/watch?etag=$taskEtag&wait=25"
                    val result = api().json(path)
                    val sid = PairCode.parse(current.getString("qr")).serverId
                    val fresh = if (result.optBoolean("changed")) parseTasks(result.getJSONArray("tasks")) else null
                    runOnUiThread {
                        if (watchActive && profile?.optString("qr") == current.optString("qr")) {
                            taskEtag = result.optString("etag")
                            if (fresh != null) { tasks.clear(); tasks.addAll(fresh); connected = true }
                            if (secure.pending(sid).isNotEmpty()) flushPending()
                        }
                    }
                } catch (_: Exception) {
                    runOnUiThread { if (watchActive) connected = false }
                    Thread.sleep(5_000)
                }
            }
        }.start()
    }

    override fun onStop() {
        watchActive = false
        super.onStop()
    }

    private fun api(): WindowsApi {
        val p = profile ?: error("Kompyuter ulanmagan")
        return WindowsApi(PairCode.parse(p.getString("qr")), p.getString("token"))
    }

    private fun work(action: () -> Unit) {
        busy = true
        Thread {
            try { action() }
            catch (e: Exception) { runOnUiThread { connected = false; notice = e.message ?: "Aloqa xatosi" } }
            finally { runOnUiThread { busy = false } }
        }.start()
    }

    private fun connect(raw: String) = work {
        val code = PairCode.parse(raw)
        val result = WindowsApi(code).pair(android.os.Build.MODEL)
        secure.save(raw, result.getString("token"), result.optString("pc_name"))
        runOnUiThread {
            profile = secure.read()
            loadHistory()
            taskEtag = ""
            tasks.clear()
            pairing = false
            notice = "Kompyuter ulandi"
        }
        refresh()
        runOnUiThread { flushPending() }
    }

    private fun refresh() = work {
        val qr = profile?.getString("qr") ?: error("Kompyuter ulanmagan")
        val session = api().json("/api/v1/session")
        val rotated = if (session.optBoolean("rotate_recommended")) {
            val freshToken = api().json("/api/v1/session/rotate", "POST", JSONObject(), UUID.randomUUID().toString()).getString("token")
            secure.updateToken(freshToken)
            runOnUiThread { profile = secure.read() }
            freshToken
        } else null
        val client = if (rotated == null) api() else WindowsApi(PairCode.parse(qr), rotated)
        val data = client.json("/api/v1/tasks?limit=30").getJSONArray("tasks")
        val fresh = parseTasks(data)
        runOnUiThread {
            tasks.clear(); tasks.addAll(fresh)
            connected = true
            notice = "${session.optString("pc_name")} • ulangan"
        }
    }

    private fun parseTasks(data: org.json.JSONArray): List<TaskView> = (0 until data.length()).map { i ->
            val t = data.getJSONObject(i)
            val files = t.optJSONArray("files")
            val steps = t.optJSONArray("steps")
            TaskView(t.optString("id"), t.optString("title"), t.optString("status"), t.optString("error"),
                if (files == null) emptyList() else (0 until files.length()).map { files.getString(it) },
                if (steps == null) emptyList() else (0 until steps.length()).map { j ->
                    steps.getJSONObject(j).let { StepView(it.optString("name"), it.optString("status"), it.optString("detail")) }
                })
    }

    private fun send(text: String) {
        if (text.isBlank()) return
        if (text.length > 4_000) { notice = "Buyruq 4000 belgidan oshmasin"; return }
        val qr = profile?.optString("qr") ?: return
        secure.queueChat(PairCode.parse(qr).serverId, UUID.randomUUID().toString(), text)
        recordMessage(text, true)
        flushPending()
    }

    private fun loadHistory() {
        messages.clear()
        val sid = profile?.optString("qr")?.takeIf { it.isNotBlank() }?.let { PairCode.parse(it).serverId } ?: return
        messages.addAll(secure.history(sid).map { Message(it.optString("text"), it.optBoolean("mine")) })
    }

    private fun recordMessage(text: String, mine: Boolean) {
        val sid = profile?.optString("qr")?.takeIf { it.isNotBlank() }?.let { PairCode.parse(it).serverId } ?: return
        secure.appendHistory(sid, text, mine)
        messages.add(Message(text, mine))
    }

    private fun flushPending() {
        if (flushing || profile == null) return
        flushing = true
        work {
            try {
                val sid = PairCode.parse(profile!!.getString("qr")).serverId
                for (item in secure.pending(sid)) {
                    try {
                        val result = api().json("/api/v1/chat", "POST", JSONObject().put("text", item.getString("text")), item.getString("id"))
                        secure.removeQueued(item.getString("id"))
                        runOnUiThread { connected = true; showChatReply(result) }
                    } catch (e: ApiFailure) {
                        if (e.errorCode in setOf("RATE_LIMITED", "INTERNAL", "AUTH_REQUIRED", "TOKEN_EXPIRED")) {
                            runOnUiThread {
                                notice = if (e.errorCode == "AUTH_REQUIRED" || e.errorCode == "TOKEN_EXPIRED")
                                    "Kompyuter bilan qaytadan bog‘laning. Buyruq navbatda." else "Kompyuter hozir band. Buyruq navbatda."
                                if (e.errorCode == "AUTH_REQUIRED" || e.errorCode == "TOKEN_EXPIRED") pairing = true
                            }
                            break
                        }
                        secure.removeQueued(item.getString("id"))
                        runOnUiThread { recordMessage(e.message ?: "Buyruq bajarilmadi", false) }
                    } catch (_: Exception) {
                        runOnUiThread { connected = false; notice = "Kompyuter javob bermayapti — buyruq navbatda" }
                        break
                    }
                }
            } finally { runOnUiThread { flushing = false } }
        }
    }

    private fun showChatReply(result: JSONObject) {
        result.optString("reply").takeIf { it.isNotBlank() }?.let { recordMessage(it, false) }
        confirmToken = result.optJSONObject("confirm")?.optString("token")?.takeIf { it.isNotBlank() }
        if (!result.isNull("task")) { tab = 2; refresh() }
        if (result.optBoolean("open_bi")) notice = "Dashboard kompyuter oynasida ochildi"
    }

    private fun answerConfirmation(yes: Boolean) {
        val token = confirmToken ?: return
        confirmToken = null
        work {
            val result = api().json("/api/v1/confirm", "POST", JSONObject().put("token", token)
                .put("yes", yes), UUID.randomUUID().toString())
            runOnUiThread { showChatReply(result) }
        }
    }

    private fun upload(uri: android.net.Uri) = work {
        var name = "fayl"
        var size = -1L
        contentResolver.query(uri, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                c.getColumnIndex(OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let { name = c.getString(it) }
                c.getColumnIndex(OpenableColumns.SIZE).takeIf { it >= 0 }?.let { size = c.getLong(it) }
            }
        }
        val result = api().upload(contentResolver, uri, name, size.takeIf { it >= 0 } ?: 50_000_000)
        runOnUiThread { recordMessage("${result.optString("name")} kompyuterga yuborildi", false); tab = 1 }
    }

    @Composable
    private fun NexvaraUi() {
        var dark by remember { mutableStateOf(true) }
        var input by remember { mutableStateOf("") }
        var manualQr by remember { mutableStateOf("") }
        var cameraUri by remember { mutableStateOf<android.net.Uri?>(null) }
        val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
            result.contents?.let { connect(it) }
        }
        val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let { upload(it) } }
        val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let { upload(it) } }
        val takePicture = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
            if (ok) cameraUri?.let { upload(it) }
        }
        fun launchCamera() {
            val folder = java.io.File(cacheDir, "camera").apply { mkdirs() }
            val file = java.io.File(folder, "photo-${UUID.randomUUID()}.jpg")
            cameraUri = FileProvider.getUriForFile(this@MainActivity, "$packageName.fileprovider", file)
            takePicture.launch(cameraUri!!)
        }
        val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) launchCamera() else notice = "Kamera ruxsati berilmadi"
        }
        val saveFile = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
            val path = pendingDownload
            if (uri != null && path != null) work {
                contentResolver.openOutputStream(uri)?.use { api().download(path, it) } ?: error("Faylni saqlab bo‘lmadi")
                runOnUiThread { notice = "Fayl saqlandi" }
            }
            pendingDownload = null
        }
        val speech = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val said = result.data?.getStringArrayListExtra(android.speech.RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
            if (said != null) input = said
        }
        val scheme = if (dark) darkColorScheme(primary = Indigo, onPrimary = Color.White, secondary = Cyan,
            background = Dark, surface = Color(0xFF121933))
            else lightColorScheme(primary = Indigo, onPrimary = Color.White, secondary = Cyan)
        MaterialTheme(colorScheme = scheme) {
            Scaffold(
                modifier = Modifier.imePadding(),
                bottomBar = {
                    if (profile != null && !pairing) NavigationBar {
                        listOf(Triple("Home", Icons.Default.Home, 0), Triple("Chat", Icons.Default.Chat, 1),
                            Triple("Tasks", Icons.Default.List, 2), Triple("Devices", Icons.Default.Devices, 3)).forEach { (label, icon, index) ->
                            NavigationBarItem(selected = tab == index, onClick = { tab = index; if (index == 2) refresh() },
                                icon = { Icon(icon, null) }, label = { Text(label) })
                        }
                    }
                }
            ) { inset ->
                Column(Modifier.fillMaxSize().padding(inset).padding(horizontal = 18.dp)) {
                    Spacer(Modifier.height(18.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(42.dp).background(Brush.linearGradient(listOf(Indigo, Cyan)), RoundedCornerShape(13.dp)), contentAlignment = Alignment.Center) {
                            Text("N", color = Color.White, fontWeight = FontWeight.Black)
                        }
                        Spacer(Modifier.width(12.dp))
                        Text("NEXVARA", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.weight(1f))
                        IconButton(onClick = { dark = !dark }) { Icon(if (dark) Icons.Default.LightMode else Icons.Default.DarkMode, "Mavzu") }
                    }
                    if (notice.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(notice, color = if (notice.contains("xato", true)) MaterialTheme.colorScheme.error else Cyan,
                            style = MaterialTheme.typography.bodySmall)
                    }
                    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                    Spacer(Modifier.height(22.dp))
                    if (profile == null || pairing) {
                        Text("Windows kompyuterni bog‘lang", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(8.dp))
                        Text("NEXVARA Windows → Devices oynasidagi QR kodni skanerlang. Bir xil Wi-Fi tarmog‘ida bo‘ling.")
                        Spacer(Modifier.height(24.dp))
                        Button(onClick = { scanner.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE).setPrompt("NEXVARA QR kodini skanerlang")) }, enabled = !busy) {
                            Icon(Icons.Default.QrCodeScanner, null); Spacer(Modifier.width(8.dp)); Text("QR skanerlash")
                        }
                        Spacer(Modifier.height(16.dp))
                        OutlinedTextField(manualQr, { manualQr = it }, label = { Text("QR havolasini joylash") }, modifier = Modifier.fillMaxWidth())
                        TextButton(onClick = { connect(manualQr) }, enabled = manualQr.isNotBlank() && !busy) { Text("Bog‘lash") }
                        if (profile != null) TextButton(onClick = { pairing = false }) { Text("Ortga") }
                    } else when (tab) {
                        0 -> {
                            Text("Xush kelibsiz", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(12.dp))
                            ElevatedCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(20.dp)) {
                                Text(profile?.optString("pc") ?: "Kompyuter", style = MaterialTheme.typography.titleLarge)
                                Text(if (connected) "Kompyuter ulangan" else "Kompyuter bilan aloqa tekshirilmagan", color = if (connected) Cyan else MaterialTheme.colorScheme.error)
                                Spacer(Modifier.height(14.dp))
                                Button(onClick = { tab = 1 }) { Text("Yangi topshiriq") }
                            } }
                            Spacer(Modifier.height(16.dp))
                            Text("Oxirgi vazifalar", style = MaterialTheme.typography.titleMedium)
                            tasks.take(3).forEach { TaskCard(it) { path -> pendingDownload = path; saveFile.launch(path.substringAfterLast('\\')) } }
                        }
                        1 -> {
                            Text("AI Chat", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                            Text("Buyruq Windows kompyuterga yuboriladi", color = Cyan)
                            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                items(messages) { m ->
                                    Surface(color = if (m.mine) Indigo else MaterialTheme.colorScheme.surfaceVariant,
                                        shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth(0.9f)) {
                                        Text(m.text, Modifier.padding(14.dp), color = if (m.mine) Color.White else MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                            if (confirmToken != null) Row {
                                Button(onClick = { answerConfirmation(true) }, enabled = !busy) { Text("Ha, davom et") }
                                Spacer(Modifier.width(10.dp))
                                OutlinedButton(onClick = { answerConfirmation(false) }, enabled = !busy) { Text("Yo‘q") }
                            }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(onClick = { filePicker.launch("*/*") }) { Icon(Icons.Default.AttachFile, "Fayl tanlash") }
                                IconButton(onClick = { imagePicker.launch("image/*") }) { Icon(Icons.Default.Image, "Rasm tanlash") }
                                IconButton(onClick = {
                                    if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
                                        launchCamera() else cameraPermission.launch(Manifest.permission.CAMERA)
                                }) { Icon(Icons.Default.PhotoCamera, "Kamera bilan rasm olish") }
                                IconButton(onClick = {
                                    val intent = android.content.Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                                        .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                        .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, "uz-UZ")
                                    try { speech.launch(intent) } catch (_: Exception) { notice = "Ovoz tanish xizmati yo‘q" }
                                }) { Icon(Icons.Default.Mic, "Ovozli buyruq") }
                                OutlinedTextField(input, { input = it }, modifier = Modifier.weight(1f), placeholder = { Text("Buyruq yozing") }, maxLines = 3)
                                IconButton(onClick = { val message = input; input = ""; send(message) }, enabled = input.isNotBlank() && !busy) {
                                    Icon(Icons.AutoMirrored.Filled.Send, "Yuborish", tint = Indigo)
                                }
                            }
                        }
                        2 -> {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("Vazifalar", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                                Spacer(Modifier.weight(1f)); IconButton(onClick = { refresh() }) { Icon(Icons.Default.Refresh, "Yangilash") }
                            }
                            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) { items(tasks) { task ->
                                TaskCard(task) { path -> pendingDownload = path; saveFile.launch(path.substringAfterLast('\\')) }
                            } }
                        }
                        3 -> {
                            Text("Qurilmalar", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(14.dp))
                            secure.all().forEach { pc ->
                                ElevatedCard(Modifier.fillMaxWidth().padding(bottom = 10.dp)) { Column(Modifier.padding(20.dp)) {
                                    Text(pc.optString("pc", "Windows PC"), style = MaterialTheme.typography.titleLarge)
                                    Text(if (profile?.optString("qr") == pc.optString("qr"))
                                        (if (connected) "Ulangan" else "Tanlangan • aloqa tekshirilmagan") else "Saqlangan kompyuter", color = Cyan)
                                    Spacer(Modifier.height(12.dp))
                                    if (profile?.optString("qr") == pc.optString("qr")) {
                                        Button(onClick = { refresh() }) { Text("Holatni tekshirish") }
                                    } else {
                                        Button(onClick = {
                                            secure.select(PairCode.parse(pc.getString("qr")).serverId)
                                            profile = secure.read(); loadHistory(); taskEtag = ""; tasks.clear(); confirmToken = null; connected = false
                                            refresh()
                                        }) { Text("Shu kompyuterni tanlash") }
                                    }
                                } }
                            }
                            TextButton(onClick = { pairing = true }) { Text("Yana bir kompyuter bog‘lash") }
                            TextButton(onClick = { work {
                                try { api().json("/api/v1/session/logout", "POST", JSONObject(), UUID.randomUUID().toString()) }
                                catch (_: Exception) { /* Local logout must work even when the PC is offline. */ }
                                secure.removeActive()
                                runOnUiThread { profile = secure.read(); connected = false; pairing = false; taskEtag = ""; tasks.clear(); messages.clear(); confirmToken = null; notice = "Qurilmadan chiqildi" }
                            } }) { Text("Tanlangan kompyuterdan chiqish") }
                        }
                    }
                }
            }
        }
    }

    @Composable
    private fun TaskCard(task: TaskView, onDownload: (String) -> Unit) {
        ElevatedCard(Modifier.fillMaxWidth().padding(top = 8.dp)) {
            Column(Modifier.padding(16.dp)) {
                Text(task.title, fontWeight = FontWeight.SemiBold)
                Text(task.status, color = when (task.status) {
                    "succeeded" -> Color(0xFF22C55E)
                    "failed" -> Color(0xFFEF4444)
                    else -> Cyan
                })
                if (task.error.isNotBlank()) Text(task.error, color = MaterialTheme.colorScheme.error)
                task.steps.forEach { step ->
                    Text("${step.name} • ${step.status}${if (step.detail.isBlank()) "" else ": ${step.detail}"}",
                        style = MaterialTheme.typography.bodySmall)
                }
                task.files.forEach { path -> TextButton(onClick = { onDownload(path) }) { Text("Faylni olish: ${path.substringAfterLast('\\')}") } }
                if (task.status == "running" || task.status == "pending") {
                    TextButton(onClick = { work {
                        api().json("/api/v1/tasks/${task.id}/cancel", "POST", JSONObject(), UUID.randomUUID().toString())
                        refresh()
                    } }) { Text("Bekor qilish") }
                }
            }
        }
    }
}
