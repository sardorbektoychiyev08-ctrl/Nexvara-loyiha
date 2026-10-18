package uz.nexvara.mobile

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/** Screens of the app. The bottom bar shows the first four; the rest open from "Bo‘limlar". */
enum class Screen(val title: String) {
    Home("Bosh sahifa"), Chat("AI suhbat"), Tasks("Vazifalar"), Sections("Bo‘limlar"),
    PcScreen("Kompyuter ekrani"), Templates("Tayyor buyruqlar"), AnswerSheets("Javob varaqalari"),
    Journal("Sinf jurnali"), Documents("Hujjat shablonlari"), Schedule("Dars jadvali"),
    Dictation("Majlis yozuvi"), Preview("Ko‘rish"), Cad("Chizma"),
    Office("Office yordamchisi"), Library("Darsliklar va testlar"), Files("Fayllar"),
    Bi("NEXVARA BI"), Workflows("Ish jarayonlari"), Teach("NEXVARA’ga o‘rgatish"),
    Memory("Xotira"), Ai("AI balans va xarajatlar"), Devices("Kompyuterlar"), Settings("Sozlamalar"),
}

enum class ThemeMode { System, Light, Dark }

/**
 * The whole app state. Every call goes to the paired Windows PC over the pinned HTTPS
 * connection (WindowsApi); nothing is computed or spent on the phone itself, so AI spend,
 * memory and Teach rules live in one place (the PC) and are never counted twice.
 */
class AppModel(app: Application) : AndroidViewModel(app) {
    val secure = SecureSession(app)
    private val prefs = app.getSharedPreferences("nexvara_ui", Context.MODE_PRIVATE)

    var profile by mutableStateOf(secure.read()); private set
    var pcs by mutableStateOf(secure.all()); private set
    var pairing by mutableStateOf(false)
    var connected by mutableStateOf<Boolean?>(null); private set
    var busy by mutableStateOf(0); private set
    var notice by mutableStateOf<String?>(null)
    var screen by mutableStateOf(Screen.Home)
    private val back = ArrayDeque<Screen>()

    var themeMode by mutableStateOf(ThemeMode.entries.getOrElse(prefs.getInt("theme", 0)) { ThemeMode.System })
        private set
    var speakReplies by mutableStateOf(prefs.getBoolean("speak", false)); private set
    var russian by mutableStateOf(prefs.getBoolean("ru", false)); private set
    fun useRussian(v: Boolean) { russian = v; prefs.edit().putBoolean("ru", v).apply() }
    var voiceLang by mutableStateOf(prefs.getString("voice_lang", "uz-UZ") ?: "uz-UZ"); private set
    fun useVoiceLang(tag: String) { voiceLang = tag; prefs.edit().putString("voice_lang", tag).apply() }
    var secureScreen by mutableStateOf(prefs.getBoolean("secure_screen", false)); private set
    var backgroundAlerts by mutableStateOf(prefs.getBoolean("bg_alerts", true)); private set
    var draft by mutableStateOf<String?>(null)  // a ready command put into the chat box
    var pcFiles by mutableStateOf<List<PcFile>>(emptyList()); private set
    var screenShot by mutableStateOf<android.graphics.Bitmap?>(null); private set
    var screenLive by mutableStateOf(false); private set
    var screenInfo by mutableStateOf(""); private set
    private var screenJob: Job? = null
    var background by mutableStateOf(false)

    val messages = mutableStateListOf<ChatMsg>()
    var confirm by mutableStateOf<ConfirmReq?>(null)
    var overview by mutableStateOf<Overview?>(null); private set
    val tasks = mutableStateListOf<TaskItem>()
    var facts by mutableStateOf<List<Fact>>(emptyList()); private set
    var rules by mutableStateOf<List<Rule>>(emptyList()); private set
    var ruleApps by mutableStateOf<Map<String, String>>(mapOf("excel" to "Excel", "word" to "Word",
        "powerpoint" to "PowerPoint", "test" to "Testlar")); private set
    var workflows by mutableStateOf<List<Workflow>>(emptyList()); private set
    var wfTemplates by mutableStateOf<List<JSONObject>>(emptyList()); private set
    var wfActive by mutableStateOf<List<WfActive>>(emptyList()); private set
    var dashboards by mutableStateOf<List<Dashboard>>(emptyList()); private set
    var biView by mutableStateOf<BiView?>(null)
    var library by mutableStateOf<Library?>(null); private set
    var ai by mutableStateOf<AiPanel?>(null); private set
    var lastUpload by mutableStateOf<String?>(null); private set
    var dictated by mutableStateOf<String?>(null)  // speech recognised by the Activity
    var afterUpload: String? = null  // a command to send once the picked photo is on the PC
    var onUploaded: ((String) -> Unit)? = null  // a tool waiting for the uploaded file's PC path
    val tools = Tools()
    val cad = CadState()
    val schedule = Schedule(app)
    var favorites by mutableStateOf(secure.favorites()); private set
    fun toggleFavorite(text: String) {
        val on = text !in favorites
        secure.setFavorite(text, on); favorites = secure.favorites()
        notice = if (on) "Sevimlilarga qo‘shildi ★" else "Sevimlilardan olindi"
    }
    /** Commands this phone sent, newest first, without repeats. */
    val recentCommands: List<String> get() = messages.filter { it.mine }.map { it.text }.asReversed().distinct().take(12)
    var preview by mutableStateOf<android.graphics.Bitmap?>(null)

    // App lock: fingerprint/face or the phone's PIN before anything is shown (on by default
    // when the phone itself has a screen lock); locks again after a minute in the background.
    private val deviceSecure = app.getSystemService(android.app.KeyguardManager::class.java)?.isDeviceSecure == true
    // Debug (test) builds start unlocked so automated tests can run; release builds lock by default.
    private val lockDefault = deviceSecure && !BuildConfig.DEBUG
    var lockEnabled by mutableStateOf(prefs.getBoolean("lock", lockDefault)); private set
    var locked by mutableStateOf(prefs.getBoolean("lock", lockDefault))
    private var stoppedAt = 0L
    var onReply: ((String) -> Unit)? = null  // voice mode reads replies aloud
    var onTaskDone: ((TaskItem) -> Unit)? = null  // notification while in the background

    private var etag = ""
    private var watcher: Job? = null
    private val phoneTasks = mutableSetOf<String>()

    init {
        loadHistory()
        if (profile != null) { refreshAll(); startWatching() }
    }

    // ---------------- navigation ----------------
    fun open(s: Screen) {
        if (s == screen) return
        if (screen == Screen.PcScreen) stopScreen()
        if (s.ordinal <= Screen.Sections.ordinal) back.clear() else back.addLast(screen)
        screen = s
        if (s == Screen.PcScreen) startScreen()
        when (s) {
            Screen.Home -> refreshAll()
            Screen.Tasks -> refreshTasks()
            Screen.Memory -> loadMemory()
            Screen.Teach -> loadTeach()
            Screen.Workflows -> loadWorkflows()
            Screen.Bi -> loadBi()
            Screen.Library -> loadLibrary()
            Screen.Ai -> loadAi()
            else -> Unit
        }
    }

    fun goBack(): Boolean {
        if (biView != null && screen == Screen.Bi) { biView = null; return true }
        if (screen == Screen.PcScreen) stopScreen()
        val prev = back.removeLastOrNull() ?: return if (screen != Screen.Home) { screen = Screen.Home; true } else false
        screen = prev
        return true
    }

    fun setTheme(m: ThemeMode) { themeMode = m; prefs.edit().putInt("theme", m.ordinal).apply() }
    fun setSpeak(v: Boolean) { speakReplies = v; prefs.edit().putBoolean("speak", v).apply() }
    fun setLock(v: Boolean) { lockEnabled = v; prefs.edit().putBoolean("lock", v).apply() }
    fun useSecureScreen(v: Boolean) { secureScreen = v; prefs.edit().putBoolean("secure_screen", v).apply() }
    fun useBackgroundAlerts(v: Boolean) { backgroundAlerts = v; prefs.edit().putBoolean("bg_alerts", v).apply() }

    /** Puts a ready command into the chat box for the user to finish and send. */
    fun compose(text: String) { draft = text; open(Screen.Chat) }

    /** How the PC is reached right now: "lan", "tailscale" or null (unknown yet). */
    val route: String?
        get() = sid?.let { WindowsApi.current(it) }?.let { if (WindowsApi.isTailnet(it)) "tailscale" else "lan" }
    val knownHosts: List<String>
        get() = profile?.optJSONArray("hosts")?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty()
    fun wentBackground() { stoppedAt = System.currentTimeMillis() }
    fun cameForeground() {
        if (lockEnabled && stoppedAt > 0 && System.currentTimeMillis() - stoppedAt > 60_000) locked = true
    }

    // ---------------- network helpers ----------------
    private fun api(): WindowsApi {
        val p = profile ?: throw ApiFailure("AUTH_REQUIRED", "Kompyuter ulanmagan")
        val hosts = p.optJSONArray("hosts")?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty()
        return WindowsApi(PairCode.parse(p.getString("qr")), p.getString("token"), hosts)
    }

    internal val sid get() = profile?.optString("qr")?.takeIf { it.isNotBlank() }?.let { PairCode.parse(it).serverId }

    /** Runs [block] on a background thread; errors become a short Uzbek notice. */
    fun <T> call(quiet: Boolean = false, block: (WindowsApi) -> T, done: (T) -> Unit = {}) {
        viewModelScope.launch {
            if (!quiet) busy++
            try {
                val out = withContext(Dispatchers.IO) { block(api()) }
                connected = true
                done(out)
            } catch (e: ApiFailure) {
                if (e.errorCode == "AUTH_REQUIRED" || e.errorCode == "TOKEN_EXPIRED") {
                    pairing = true
                    notice = "Kompyuter bilan qaytadan bog‘laning (QR kod)."
                } else if (!quiet) notice = e.message
            } catch (e: Exception) {
                connected = false
                if (!quiet) notice = "Kompyuter javob bermayapti. Wi-Fi va NEXVARA ochiqligini tekshiring."
            } finally { if (!quiet) busy-- }
        }
    }

    internal fun post(path: String, body: JSONObject = JSONObject()) =
        { a: WindowsApi -> a.json(path, "POST", body, UUID.randomUUID().toString()) }

    internal fun get(path: String) = { a: WindowsApi -> a.json(path) }

    // ---------------- pairing / PCs ----------------
    fun connect(raw: String) {
        viewModelScope.launch {
            busy++
            try {
                val code = PairCode.parse(raw)
                val result = withContext(Dispatchers.IO) { WindowsApi(code).pair(android.os.Build.MODEL) }
                secure.save(raw, result.getString("token"), result.optString("pc_name"))
                secure.updateHosts(WindowsApi.hostsFrom(result.optJSONObject("hosts_info")))
                switched()
                pairing = false
                notice = "Kompyuter ulandi ✓"
            } catch (e: IllegalArgumentException) {
                notice = e.message ?: "QR kod noto‘g‘ri"
            } catch (e: ApiFailure) {
                notice = e.message
            } catch (e: Exception) {
                notice = "Kompyuterga ulanib bo‘lmadi. Bir xil Wi-Fi tarmog‘ida ekaningizni tekshiring."
            } finally { busy-- }
        }
    }

    fun selectPc(serverId: String) { secure.select(serverId); switched() }

    fun renamePc(serverId: String, label: String) { secure.rename(serverId, label); pcs = secure.all(); profile = secure.read() }

    fun logoutPc() {
        viewModelScope.launch {
            busy++
            try {
                withContext(Dispatchers.IO) {
                    try { api().json("/api/v1/session/logout", "POST", JSONObject(), UUID.randomUUID().toString()) }
                    catch (_: Exception) { /* local logout must work while the PC is off */ }
                }
                secure.removeActive()
                switched()
                notice = "Kompyuterdan chiqildi"
            } finally { busy-- }
        }
    }

    private fun switched() {
        profile = secure.read(); pcs = secure.all()
        etag = ""; tasks.clear(); confirm = null; overview = null; connected = null
        facts = emptyList(); rules = emptyList(); workflows = emptyList(); dashboards = emptyList()
        biView = null; library = null; ai = null
        loadHistory()
        if (profile != null) { refreshAll(); startWatching(); flushPending() } else watcher?.cancel()
    }

    // ---------------- home / tasks ----------------
    fun refreshAll() {
        if (profile == null) return
        call(quiet = overview != null, block = { a ->
            val s = a.json("/api/v1/session")
            secure.updateHosts(WindowsApi.hostsFrom(s))  // reconnect later from another network
            secure.updateWake(s.optJSONObject("wake"))  // wake this PC later (Wake-on-LAN)
            if (s.optBoolean("rotate_recommended")) {
                val fresh = a.json("/api/v1/session/rotate", "POST", JSONObject(), UUID.randomUUID().toString()).getString("token")
                secure.updateToken(fresh)
            }
            Parse.overview(api().json("/api/v1/overview"))
        }) { ov ->
            profile = secure.read()
            overview = ov
            if (tasks.isEmpty()) tasks.addAll(ov.tasks)
            flushPending()
            syncHistory()
        }
    }

    fun refreshTasks() = call(quiet = true, block = { Parse.tasks(it.json("/api/v1/tasks?limit=40").optJSONArray("tasks")) }) {
        tasks.clear(); tasks.addAll(it)
    }

    private fun startWatching() {
        watcher?.cancel()
        watcher = viewModelScope.launch {
            while (isActive) {
                val p = profile ?: break
                try {
                    val r = withContext(Dispatchers.IO) { api().json("/api/v1/tasks/watch?etag=$etag&wait=25") }
                    if (profile !== p) continue
                    connected = true
                    etag = r.optString("etag")
                    if (r.optBoolean("changed")) mergeTasks(Parse.tasks(r.optJSONArray("tasks")))
                    if (secure.pending(sid ?: "").isNotEmpty()) flushPending()
                } catch (e: ApiFailure) {
                    if (e.errorCode == "AUTH_REQUIRED" || e.errorCode == "TOKEN_EXPIRED") { pairing = true; break }
                    delay(5_000)
                } catch (_: Exception) {
                    connected = false
                    delay(if (background) 30_000 else 5_000)
                }
            }
        }
    }

    private fun mergeTasks(fresh: List<TaskItem>) {
        val before = tasks.associateBy { it.id }
        for (t in fresh) {
            val old = before[t.id]
            if (old != null && old.active && !t.active && t.id in phoneTasks) {
                phoneTasks.remove(t.id)
                onTaskDone?.invoke(t)
            }
        }
        val ids = fresh.map { it.id }.toSet()
        val older = tasks.filter { it.id !in ids }
        tasks.clear(); tasks.addAll(fresh + older)
    }

    fun cancelTask(t: TaskItem) = call(block = post("/api/v1/tasks/${t.id}/cancel")) { refreshTasks() }
    fun pauseTask(t: TaskItem) = call(block = post("/api/v1/tasks/${t.id}/pause")) {
        notice = "Pauza: vazifa joriy qadamni tugatib to‘xtaydi"; refreshTasks()
    }
    fun resumeTask(t: TaskItem) = call(block = post("/api/v1/tasks/${t.id}/resume")) { refreshTasks() }

    private fun track(task: JSONObject?) {
        if (task == null) return
        val t = Parse.task(task)
        phoneTasks += t.id
        mergeTasks(listOf(t))
    }

    // ---------------- chat ----------------
    private fun loadHistory() {
        messages.clear()
        val s = sid ?: return
        messages.addAll(secure.history(s).map { ChatMsg(it.optString("text"), it.optBoolean("mine")) })
    }

    internal fun record(text: String, mine: Boolean) {
        val s = sid ?: return
        secure.appendHistory(s, text, mine)
        messages.add(ChatMsg(text, mine))
    }

    /** Chat on the PC since this phone last looked (also messages typed on the PC). */
    private fun syncHistory() {
        val s = sid ?: return
        val after = secure.historyCursor(s)
        call(quiet = true, block = { it.json("/api/v1/chat/history?limit=100&after=$after").optJSONArray("messages") ?: JSONArray() }) { arr ->
            if (arr.length() == 0) return@call
            val last = arr.getJSONObject(arr.length() - 1).optInt("id")
            if (after > 0) {
                // Only what was said on the PC itself; the phone's own lines are already here.
                val mine = messages.map { it.text }.toSet()
                for (i in 0 until arr.length()) {
                    val m = arr.getJSONObject(i)
                    val text = m.optString("text")
                    if (text !in mine) record(if (m.optString("role") == "user") "💻 $text" else text, false)
                }
            }
            secure.setHistoryCursor(s, last)
        }
    }

    fun send(text: String, inBackground: Boolean = false) {
        val clean = text.trim()
        if (clean.isEmpty()) return
        if (clean.length > 4000) { notice = "Buyruq 4000 belgidan oshmasin"; return }
        val s = sid ?: return
        val full = if (inBackground && !clean.contains("fonda", true)) "$clean, fonda bajar" else clean
        secure.queueChat(s, UUID.randomUUID().toString(), full)
        record(full, true)
        flushPending()
    }

    private var flushing = false
    fun flushPending() {
        val s = sid ?: return
        if (flushing) return
        flushing = true
        viewModelScope.launch {
            try {
                for (item in secure.pending(s)) {
                    try {
                        val r = withContext(Dispatchers.IO) {
                            api().json("/api/v1/chat", "POST", JSONObject().put("text", item.getString("text")), item.getString("id"))
                        }
                        secure.removeQueued(item.getString("id"))
                        connected = true
                        showReply(r)
                    } catch (e: ApiFailure) {
                        if (e.errorCode in setOf("RATE_LIMITED", "INTERNAL", "AUTH_REQUIRED", "TOKEN_EXPIRED")) {
                            val auth = e.errorCode == "AUTH_REQUIRED" || e.errorCode == "TOKEN_EXPIRED"
                            notice = if (auth) "Kompyuter bilan qaytadan bog‘laning. Buyruq navbatda." else "Kompyuter band. Buyruq navbatda."
                            if (auth) pairing = true
                            break
                        }
                        secure.removeQueued(item.getString("id"))
                        record(e.message ?: "Buyruq bajarilmadi", false)
                    } catch (_: Exception) {
                        connected = false
                        notice = "Kompyuter javob bermayapti — buyruq navbatda, aloqa tiklanganda yuboriladi"
                        break
                    }
                }
            } finally { flushing = false }
        }
    }

    val queued get() = sid?.let { secure.pending(it).size } ?: 0

    private fun showReply(r: JSONObject) {
        val reply = r.optString("reply")
        if (reply.isNotBlank()) { record(reply, false); onReply?.invoke(reply) }
        confirm = r.optJSONObject("confirm")?.let { ConfirmReq(it.optString("token"), it.optString("text")) }
            ?.takeIf { it.token.isNotBlank() }
        track(r.optJSONObject("task"))
        if (r.optBoolean("open_bi")) notice = "Dashboard kompyuter ekranida ochildi"
    }

    fun answer(yes: Boolean) {
        val c = confirm ?: return
        confirm = null
        record(if (yes) "Ha, davom et" else "Yo‘q", true)
        call(block = post("/api/v1/confirm", JSONObject().put("token", c.token).put("yes", yes))) { showReply(it) }
    }

    // ---------------- files ----------------
    fun upload(uri: android.net.Uri) {
        val ctx = getApplication<Application>()
        var name = "fayl"
        var size = -1L
        ctx.contentResolver.query(uri, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let { name = c.getString(it) }
                c.getColumnIndex(android.provider.OpenableColumns.SIZE).takeIf { it >= 0 }?.let { size = c.getLong(it) }
            }
        }
        call(block = { it.upload(ctx.contentResolver, uri, name, size.takeIf { s -> s >= 0 } ?: 50_000_000) }) { r ->
            lastUpload = r.optString("path")
            record("📎 «${r.optString("name")}» kompyuterga yuborildi. Endi u bilan nima qilishni yozing.", false)
            onUploaded?.let { cb -> onUploaded = null; cb(r.optString("path")) }
            afterUpload?.let { cmd -> afterUpload = null; send(cmd); open(Screen.Chat) }
        }
    }

    fun download(path: String, target: android.net.Uri) {
        val ctx = getApplication<Application>()
        call(block = { a -> ctx.contentResolver.openOutputStream(target)?.use { a.download(path, it) } ?: error("Saqlab bo‘lmadi") }) {
            notice = "Fayl telefonga saqlandi ✓"
        }
    }

    /** Shows a result picture (a drawing's PNG) inside the app; the copy is deleted after. */
    fun previewImage(path: String) {
        val ctx = getApplication<Application>()
        call(block = { a ->
            val f = java.io.File(ctx.cacheDir, "preview-${UUID.randomUUID()}.img")
            try {
                f.outputStream().use { a.download(path, it) }
                android.graphics.BitmapFactory.decodeFile(f.path) ?: error("Rasmni ochib bo‘lmadi")
            } finally { f.delete() }
        }) { preview = it }
    }

    val results: List<Pair<TaskItem, String>>
        get() = tasks.flatMap { t -> t.files.map { t to it } }

    // ---------------- sections ----------------
    fun loadAi() = call(quiet = ai != null, block = get("/api/v1/ai")) { ai = Parse.ai(it) }
    fun refreshBalance(p: AiProvider) = call(block = post("/api/v1/ai/${p.id}/balance")) {
        if (!it.optBoolean("supported")) notice = "${p.label}: rasmiy balans API yo‘q — sarfni provayder sahifasida ko‘ring"
        loadAi()
    }

    fun loadMemory() = call(quiet = facts.isNotEmpty(), block = get("/api/v1/memory")) { facts = Parse.facts(it.optJSONArray("facts")) }
    fun addFact(text: String) = call(block = post("/api/v1/memory", JSONObject().put("text", text))) {
        facts = Parse.facts(it.optJSONArray("facts")); notice = "Eslab qolindi ✓"
    }
    fun editFact(f: Fact, text: String) = call(block = post("/api/v1/memory/${f.id}", JSONObject().put("text", text))) {
        facts = Parse.facts(it.optJSONArray("facts"))
    }
    fun deleteFact(f: Fact) = call(block = post("/api/v1/memory/${f.id}/delete")) { facts = Parse.facts(it.optJSONArray("facts")) }
    fun searchMemory(q: String, done: (List<String>) -> Unit) = call(block = get("/api/v1/memory/search?q=" + java.net.URLEncoder.encode(q, "UTF-8"))) {
        val a = it.optJSONArray("results") ?: JSONArray()
        done((0 until a.length()).map { i -> a.getJSONObject(i).optString("text") })
    }

    fun loadTeach() = call(quiet = rules.isNotEmpty(), block = get("/api/v1/teach")) {
        rules = Parse.rules(it.optJSONArray("rules"))
        it.optJSONObject("apps")?.let { apps -> ruleApps = apps.keys().asSequence().associateWith { k -> apps.optString(k) } }
    }
    fun previewRule(app: String, text: String, done: (Boolean, String) -> Unit) =
        call(block = post("/api/v1/teach", JSONObject().put("app", app).put("text", text).put("preview", true))) {
            val acts = it.optJSONArray("actions")
            val list = if (acts == null) "" else (0 until acts.length()).joinToString("\n") { i -> "• " + acts.optString(i) }
            done(it.optBoolean("ok"), it.optString("error").ifBlank { list })
        }
    fun addRule(app: String, text: String) = call(block = post("/api/v1/teach", JSONObject().put("app", app).put("text", text))) {
        rules = Parse.rules(it.optJSONArray("rules")); notice = "Qoida saqlandi ✓"
    }
    fun toggleRule(r: Rule, on: Boolean) = call(block = post("/api/v1/teach/${r.id}", JSONObject().put("enabled", on))) {
        rules = Parse.rules(it.optJSONArray("rules"))
    }
    fun deleteRule(r: Rule) = call(block = post("/api/v1/teach/${r.id}/delete")) { rules = Parse.rules(it.optJSONArray("rules")) }

    fun loadWorkflows() = call(quiet = workflows.isNotEmpty(), block = get("/api/v1/workflows")) {
        workflows = Parse.workflows(it.optJSONArray("workflows"))
        val t = it.optJSONArray("templates") ?: JSONArray()
        wfTemplates = (0 until t.length()).map { i -> t.getJSONObject(i) }
        wfActive = Parse.active(it.optJSONArray("active"))
    }
    fun saveWorkflow(data: JSONObject, done: () -> Unit = {}) = call(block = post("/api/v1/workflows", data)) {
        workflows = Parse.workflows(it.optJSONArray("workflows")); notice = "Ish jarayoni saqlandi ✓"; done()
    }
    fun runWorkflow(w: Workflow) {
        val body = JSONObject()
        if (w.trigger == "folder") {
            val f = lastUpload
            if (f == null) { notice = "Bu jarayon fayl bilan ishlaydi: avval Fayllar bo‘limidan fayl yuboring"; return }
            body.put("file", f)
        }
        call(block = post("/api/v1/workflows/${w.id}/run", body)) {
            notice = "«${w.name}» kompyuterda boshlandi"
            loadWorkflows(); refreshTasks()
        }
    }
    fun deleteWorkflow(w: Workflow) = call(block = post("/api/v1/workflows/${w.id}/delete")) {
        workflows = Parse.workflows(it.optJSONArray("workflows"))
    }
    fun runAction(a: WfActive, action: String) = call(block = post("/api/v1/workflows/runs/${a.runId}/$action")) {
        wfActive = Parse.active(it.optJSONArray("active"))
    }

    fun loadBi() = call(quiet = dashboards.isNotEmpty(), block = get("/api/v1/bi")) { dashboards = Parse.dashboards(it.optJSONArray("dashboards")) }
    fun openBi(d: Dashboard, page: Int = 0, onPc: Boolean = true) =
        call(block = post("/api/v1/bi/open", JSONObject().put("file", d.file).put("show_on_pc", onPc)
            .put("state", JSONObject().put("page", page)))) {
            biView = Parse.bi(it)
            if (onPc) notice = "Kompyuter ekranida ham ochildi"
        }

    fun loadLibrary() = call(quiet = library != null, block = get("/api/v1/library")) { library = Parse.library(it) }
    fun makeTest(grade: Int?, subject: String?, topic: String, count: Int, variants: Int, useAi: Boolean) {
        val b = JSONObject().put("topic", topic).put("count", count).put("variants", variants).put("ai", useAi)
        grade?.let { b.put("grade", it) }
        subject?.let { b.put("subject", it) }
        call(block = post("/api/v1/library/test", b)) { r ->
            r.optJSONObject("confirm")?.let { confirm = ConfirmReq(it.optString("token"), it.optString("text")); screen = Screen.Chat }
            r.optJSONObject("task")?.let { track(it); notice = "Test kompyuterda tuzilmoqda (Word ekranda ochiladi)"; open(Screen.Tasks) }
        }
    }

    fun office(kind: String) = call(block = post("/api/v1/office/$kind")) { r ->
        track(r.optJSONObject("task")); notice = "Kompyuter ekranida bajarilmoqda"; open(Screen.Tasks)
    }

    // ---------------- the PC screen (view only, refreshed while the screen is open) ----------------
    fun startScreen() {
        screenJob?.cancel()
        screenLive = true
        screenJob = viewModelScope.launch {
            var fails = 0
            while (isActive && screenLive) {
                try {
                    val data = withContext(Dispatchers.IO) { api().bytes("/api/v1/screen") }
                    val bmp = withContext(Dispatchers.Default) { android.graphics.BitmapFactory.decodeByteArray(data, 0, data.size) }
                    if (bmp != null) { screenShot = bmp; screenInfo = "Yangilandi"; fails = 0 }
                    connected = true
                } catch (e: ApiFailure) {
                    screenInfo = e.message ?: "Ekranni olib bo‘lmadi"
                    if (e.errorCode == "NOT_FOUND") { screenLive = false; break }
                } catch (_: Exception) {
                    fails++
                    screenInfo = "Kompyuter javob bermayapti"
                    if (fails > 5) { screenLive = false; break }
                }
                delay(if (background) 5_000 else 1_200)
            }
        }
    }

    fun stopScreen() { screenLive = false; screenJob?.cancel() }

    // ---------------- PC files ----------------
    fun searchPc(q: String, ext: String = "") = call(block = get(
        "/api/v1/files/search?q=" + java.net.URLEncoder.encode(q, "UTF-8") + "&ext=" + java.net.URLEncoder.encode(ext, "UTF-8"))) {
        pcFiles = Parse.pcFiles(it.optJSONArray("files"))
        if (pcFiles.isEmpty()) notice = "Hech narsa topilmadi"
    }
    fun openOnPc(f: PcFile) = call(block = post("/api/v1/files/open", JSONObject().put("path", f.path))) {
        notice = "«${f.name}» kompyuter ekranida ochildi"
    }
    fun shareToPhone(f: PcFile, then: (String) -> Unit) = call(block = post("/api/v1/files/share", JSONObject().put("path", f.path))) {
        then(it.optString("path"))
    }

    fun linkGoogle(idToken: String) = call(block = post("/api/v1/account/link", JSONObject().put("id_token", idToken))) {
        notice = "Google hisobi bog‘landi: ${it.optString("email")}"; refreshAll()
    }

    override fun onCleared() { watcher?.cancel(); super.onCleared() }
}
