package uz.nexvara.mobile

import android.os.Bundle
import android.provider.OpenableColumns
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
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import org.json.JSONObject
import java.util.UUID

private val Indigo = Color(0xFF6366F1)
private val Cyan = Color(0xFF06B6D4)
private val Dark = Color(0xFF0B1020)
private data class Message(val text: String, val mine: Boolean)
private data class TaskView(val id: String, val title: String, val status: String, val error: String, val files: List<String>)

class MainActivity : ComponentActivity() {
    private lateinit var secure: SecureSession
    private var profile by mutableStateOf<JSONObject?>(null)
    private var pairing by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var notice by mutableStateOf("")
    private var tab by mutableStateOf(0)
    private val messages = mutableStateListOf<Message>()
    private val tasks = mutableStateListOf<TaskView>()
    private var pendingDownload by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        secure = SecureSession(this)
        profile = secure.read()
        setContent { NexvaraUi() }
        if (profile != null) refresh()
    }

    private fun api(): WindowsApi {
        val p = profile ?: error("Kompyuter ulanmagan")
        return WindowsApi(PairCode.parse(p.getString("qr")), p.getString("token"))
    }

    private fun work(action: () -> Unit) {
        busy = true
        Thread {
            try { action() }
            catch (e: Exception) { runOnUiThread { notice = e.message ?: "Aloqa xatosi" } }
            finally { runOnUiThread { busy = false } }
        }.start()
    }

    private fun connect(raw: String) = work {
        val code = PairCode.parse(raw)
        val result = WindowsApi(code).pair(android.os.Build.MODEL)
        secure.save(raw, result.getString("token"), result.optString("pc_name"))
        runOnUiThread {
            profile = secure.read()
            pairing = false
            notice = "Kompyuter ulandi"
        }
        refresh()
    }

    private fun refresh() = work {
        val session = api().json("/api/v1/session")
        val data = api().json("/api/v1/tasks?limit=30").getJSONArray("tasks")
        val fresh = (0 until data.length()).map { i ->
            val t = data.getJSONObject(i)
            val files = t.optJSONArray("files")
            TaskView(t.optString("id"), t.optString("title"), t.optString("status"), t.optString("error"),
                if (files == null) emptyList() else (0 until files.length()).map { files.getString(it) })
        }
        runOnUiThread {
            tasks.clear(); tasks.addAll(fresh)
            notice = "${session.optString("pc_name")} • ulangan"
        }
    }

    private fun send(text: String) {
        if (text.isBlank()) return
        messages.add(Message(text, true))
        work {
            val result = api().json("/api/v1/chat", "POST", JSONObject().put("text", text), UUID.randomUUID().toString())
            runOnUiThread {
                messages.add(Message(result.optString("reply", "Javob olindi"), false))
                if (!result.isNull("task")) { tab = 2; refresh() }
                if (!result.isNull("confirm")) notice = "Tasdiq talab qilinadi. Hozircha Windows oynasida tasdiqlang."
            }
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
        runOnUiThread { messages.add(Message("${result.optString("name")} kompyuterga yuborildi", false)); tab = 1 }
    }

    @Composable
    private fun NexvaraUi() {
        var dark by remember { mutableStateOf(true) }
        var input by remember { mutableStateOf("") }
        var manualQr by remember { mutableStateOf("") }
        val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
            result.contents?.let { connect(it) }
        }
        val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let { upload(it) } }
        val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let { upload(it) } }
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
        val scheme = if (dark) darkColorScheme(primary = Indigo, secondary = Cyan, background = Dark, surface = Color(0xFF121933))
            else lightColorScheme(primary = Indigo, secondary = Cyan)
        MaterialTheme(colorScheme = scheme) {
            Scaffold(
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
                                Text("Vazifalar Windows NEXVARA orqali bajariladi", color = Cyan)
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
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(onClick = { filePicker.launch("*/*") }) { Icon(Icons.Default.AttachFile, "Fayl tanlash") }
                                IconButton(onClick = { imagePicker.launch("image/*") }) { Icon(Icons.Default.Image, "Rasm tanlash") }
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
                            ElevatedCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(20.dp)) {
                                Text(profile?.optString("pc") ?: "Windows PC", style = MaterialTheme.typography.titleLarge)
                                Text("Sertifikat QR orqali tekshiriladi", color = Cyan)
                                Spacer(Modifier.height(12.dp))
                                Button(onClick = { refresh() }) { Text("Holatni tekshirish") }
                            } }
                            TextButton(onClick = { pairing = true }) { Text("Yana bir kompyuter bog‘lash") }
                            TextButton(onClick = { work {
                                api().json("/api/v1/session/logout", "POST", JSONObject(), UUID.randomUUID().toString())
                                secure.clear(); runOnUiThread { profile = null; pairing = false; tasks.clear(); messages.clear() }
                            } }) { Text("Chiqish") }
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
