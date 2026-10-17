package uz.nexvara.mobile

import org.json.JSONArray
import org.json.JSONObject

/** What the Windows Agent sends (docs/api/openapi.yaml), parsed into plain Kotlin values. */

data class StepItem(val name: String, val status: String, val detail: String)

data class TaskItem(
    val id: String, val title: String, val status: String, val error: String,
    val files: List<String>, val steps: List<StepItem>, val pauseRequested: Boolean,
    val cancelRequested: Boolean, val createdAt: Double, val finishedAt: Double?,
) {
    val active get() = status in ACTIVE
    companion object { val ACTIVE = setOf("pending", "running", "paused") }
}

data class ChatMsg(val text: String, val mine: Boolean)

data class ConfirmReq(val token: String, val text: String)

data class AiProvider(
    val id: String, val label: String, val hasKey: Boolean, val spentToday: Double,
    val spentMonth: Double, val dailyLimit: Double?, val monthlyLimit: Double?,
    val leftToday: Double?, val leftMonth: Double?, val balanceApi: Boolean,
    val balance: String?, val billingUrl: String, val usageUrl: String, val keyUrl: String,
    val freeTier: String,
)

data class AiUse(val ts: Double, val provider: String, val purpose: String, val cost: Double)

data class AiPanel(
    val enabled: Boolean, val ready: Boolean, val spentToday: Double, val spentMonth: Double,
    val dailyBudget: Double, val monthlyBudget: Double, val warnings: List<String>,
    val providers: List<AiProvider>, val history: List<AiUse>, val series: List<Pair<String, Double>>,
)

data class SyncInfo(
    val available: Boolean, val enabled: Boolean, val folderName: String,
    val googleDrive: Boolean, val hasPassphrase: Boolean, val last: Double,
)

data class AccountInfo(
    val pcConfigured: Boolean, val pcSignedIn: Boolean, val pcEmail: String, val ownerSet: Boolean,
    val webClientId: String, val phoneReady: Boolean, val linkedEmail: String,
)

data class Overview(
    val pcName: String, val version: String, val tasks: List<TaskItem>, val running: Int,
    val counts: Map<String, Int?>, val ai: AiPanel, val sync: SyncInfo, val account: AccountInfo,
)

data class Fact(val id: Int, val text: String, val updated: Double)

data class Rule(
    val id: Int, val app: String, val appLabel: String, val text: String, val enabled: Boolean,
    val version: Int, val actions: List<String>, val problem: String,
)

data class WfStep(val kind: String, val text: String, val seconds: Int)

data class Workflow(
    val id: Int, val name: String, val trigger: String, val time: String, val folder: String,
    val steps: List<WfStep>, val enabled: Boolean, val lastStatus: String, val raw: JSONObject,
)

data class WfActive(val runId: Int, val name: String, val paused: Boolean, val waitingApproval: Boolean)

data class Dashboard(val file: String, val name: String, val sourceName: String, val saved: Double)

data class Series(val name: String, val values: List<Double?>)

data class Widget(
    val type: String, val title: String, val value: Double?, val unit: String, val growth: Double?,
    val growthLabel: String, val labels: List<String>, val values: List<Double?>,
    val series: List<Series>, val columns: List<String>, val rows: List<List<String>>,
)

data class BiView(
    val name: String, val file: String, val page: Int, val pages: List<String>,
    val widgets: List<Widget>, val problems: List<String>, val rows: Int, val totalRows: Int,
)

data class Book(val label: String, val grade: Int, val subject: String, val pages: Int)

data class Library(val books: List<Book>, val catalog: Map<Int, List<String>>)

data class PcFile(val path: String, val name: String, val folder: String, val ext: String, val size: Long, val modified: Double)

object Parse {
    private fun JSONArray?.objects(): List<JSONObject> =
        if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

    private fun JSONArray?.strings(): List<String> =
        if (this == null) emptyList() else (0 until length()).map { optString(it) }

    private fun JSONObject.dbl(key: String): Double? =
        if (isNull(key) || !has(key)) null else optDouble(key).takeUnless { it.isNaN() }

    private fun JSONObject.str(key: String): String = if (isNull(key)) "" else optString(key)

    fun task(o: JSONObject) = TaskItem(
        o.str("id"), o.str("title"), o.optString("status", "pending"), o.str("error"),
        o.optJSONArray("files").strings(),
        o.optJSONArray("steps").objects().map { StepItem(it.str("name"), it.str("status"), it.str("detail")) },
        o.optBoolean("pause_requested"), o.optBoolean("cancel_requested"),
        o.optDouble("created_at", 0.0), o.dbl("finished_at"),
    )

    fun tasks(a: JSONArray?) = a.objects().map(::task)

    private fun balanceText(b: JSONObject?): String? {
        if (b == null || !b.optBoolean("supported")) return null
        if (b.has("error")) return b.optString("error")
        return b.optJSONArray("balances").objects().joinToString(", ") {
            usFmt("%.2f %s", it.optDouble("total"), it.optString("currency"))
        }.ifBlank { null }
    }

    fun provider(id: String, o: JSONObject) = AiProvider(
        id, o.optString("label", id), o.optBoolean("has_key"), o.optDouble("spent_today", 0.0),
        o.optDouble("spent_month", 0.0), o.dbl("daily_limit"), o.dbl("monthly_limit"),
        o.dbl("left_today"), o.dbl("left_month"), o.optBoolean("balance_api"),
        balanceText(o.optJSONObject("balance")), o.str("billing_url"), o.str("usage_url"),
        o.str("key_url"), o.str("free_tier"),
    )

    fun ai(o: JSONObject?): AiPanel {
        val d = o ?: JSONObject()
        val provs = d.optJSONObject("providers") ?: JSONObject()
        return AiPanel(
            d.optBoolean("enabled"), d.optBoolean("ready"), d.optDouble("spent_today", 0.0),
            d.optDouble("spent_month", 0.0), d.optDouble("daily_budget_usd", 0.0),
            d.optDouble("monthly_budget_usd", 0.0), d.optJSONArray("warnings").strings(),
            provs.keys().asSequence().toList().map { provider(it, provs.getJSONObject(it)) },
            d.optJSONArray("history").objects().map {
                AiUse(it.optDouble("ts"), it.str("provider"), it.str("purpose"), it.optDouble("cost", 0.0))
            },
            d.optJSONArray("series").objects().map { it.str("day") to it.optDouble("total", 0.0) },
        )
    }

    fun overview(o: JSONObject): Overview {
        val c = o.optJSONObject("counts") ?: JSONObject()
        val s = o.optJSONObject("sync") ?: JSONObject()
        val acc = o.optJSONObject("account") ?: JSONObject()
        return Overview(
            o.str("pc_name"), o.str("app_version"), tasks(o.optJSONArray("tasks")), o.optInt("running"),
            c.keys().asSequence().associateWith { k -> if (c.isNull(k)) null else c.optInt(k) },
            ai(o.optJSONObject("ai")), sync(s), account(acc),
        )
    }

    fun sync(s: JSONObject) = SyncInfo(
        s.optBoolean("available"), s.optBoolean("enabled"), s.str("folder_name"),
        s.optBoolean("google_drive"), s.optBoolean("has_passphrase"), s.optDouble("last", 0.0),
    )

    fun account(a: JSONObject): AccountInfo {
        val pc = a.optJSONObject("pc") ?: JSONObject()
        val ph = a.optJSONObject("phone") ?: JSONObject()
        return AccountInfo(
            pc.optBoolean("configured"), pc.optBoolean("signed_in"), pc.str("email"),
            pc.optBoolean("owner_set"), ph.str("web_client_id"), ph.optBoolean("ready"),
            ph.str("linked_email"),
        )
    }

    fun facts(a: JSONArray?) = a.objects().map { Fact(it.optInt("id"), it.str("text"), it.optDouble("updated")) }

    fun rules(a: JSONArray?) = a.objects().map {
        Rule(it.optInt("id"), it.str("app"), it.str("app_label"), it.str("text"), it.optBoolean("enabled"),
            it.optInt("version"), it.optJSONArray("actions").strings(), it.str("problem"))
    }

    fun workflows(a: JSONArray?) = a.objects().map {
        val t = it.optJSONObject("trigger") ?: JSONObject()
        Workflow(
            it.optInt("id"), it.str("name"), t.optString("type", "manual"), t.str("time"), t.str("folder"),
            it.optJSONArray("steps").objects().map { s -> WfStep(s.str("kind"), s.str("text"), s.optInt("seconds")) },
            it.optBoolean("enabled", true), it.optJSONObject("last_run")?.str("status").orEmpty(), it,
        )
    }

    fun active(a: JSONArray?) = a.objects().map {
        WfActive(it.optInt("run_id"), it.str("name"), it.optBoolean("paused"), it.optBoolean("waiting_approval"))
    }

    fun dashboards(a: JSONArray?) = a.objects().map {
        Dashboard(it.str("file"), it.optString("name", "Dashboard"), it.str("source_name"), it.optDouble("saved", 0.0))
    }

    private fun cell(v: Any?): String = when (v) {
        null, JSONObject.NULL -> ""
        is Number -> v.toDouble().let { d -> if (d == Math.floor(d) && kotlin.math.abs(d) < 1e15) d.toLong().toString() else usFmt("%.2f", d) }
        else -> v.toString()
    }

    private fun numbers(a: JSONArray?): List<Double?> =
        if (a == null) emptyList() else (0 until a.length()).map { if (a.isNull(it)) null else a.optDouble(it) }

    fun widget(o: JSONObject) = Widget(
        o.str("type"), o.str("title"), o.dbl("value"), o.str("unit"), o.dbl("growth"), o.str("growth_label"),
        o.optJSONArray("labels").strings(), numbers(o.optJSONArray("values")),
        o.optJSONArray("series").objects().map { Series(it.str("name"), numbers(it.optJSONArray("values"))) },
        o.optJSONArray("columns").strings(),
        o.optJSONArray("rows").let { rows ->
            if (rows == null) emptyList() else (0 until rows.length()).map { i ->
                val r = rows.optJSONArray(i) ?: JSONArray()
                (0 until r.length()).map { cell(r.opt(it)) }
            }
        },
    )

    fun bi(o: JSONObject) = BiView(
        o.str("name"), o.str("file"), o.optInt("page"), o.optJSONArray("pages").strings(),
        o.optJSONArray("widgets").objects().map(::widget), o.optJSONArray("problems").strings(),
        o.optInt("rows"), o.optInt("total_rows"),
    )

    fun pcFiles(a: JSONArray?) = a.objects().map {
        PcFile(it.str("path"), it.str("name"), it.str("folder"), it.str("ext"), it.optLong("size"), it.optDouble("modified", 0.0))
    }

    fun library(o: JSONObject): Library {
        val cat = o.optJSONObject("catalog") ?: JSONObject()
        return Library(
            o.optJSONArray("books").objects().map {
                Book(it.str("label"), it.optInt("grade"), it.str("subject"), it.optInt("pages"))
            },
            cat.keys().asSequence().mapNotNull { k -> k.toIntOrNull()?.let { it to cat.optJSONArray(k).strings() } }
                .toMap().toSortedMap(),
        )
    }
}

/** Money and time in Uzbek. */
object Fmt {
    fun usd(v: Double?): String = if (v == null) "—" else "$" + usFmt("%.2f", v)
    fun usdFine(v: Double?): String = if (v == null) "—" else if (v < 0.1) "$" + usFmt("%.3f", v) else usd(v)

    fun status(s: String) = when (s) {
        "pending" -> "Kutilmoqda"
        "running" -> "Bajarilmoqda"
        "paused" -> "Pauzada"
        "succeeded" -> "Bajarildi"
        "failed" -> "Xatolik"
        "cancelled" -> "Bekor qilindi"
        else -> s
    }

    fun ago(ts: Double): String {
        if (ts <= 0) return "hali yo‘q"
        val s = (System.currentTimeMillis() / 1000.0 - ts).toLong()
        return when {
            s < 60 -> "hozirgina"
            s < 3600 -> "${s / 60} daqiqa oldin"
            s < 86_400 -> "${s / 3600} soat oldin"
            else -> "${s / 86_400} kun oldin"
        }
    }

    fun size(b: Long): String = when {
        b >= 1_048_576 -> usFmt("%.1f MB", b / 1_048_576.0)
        b >= 1024 -> "${b / 1024} KB"
        else -> "$b bayt"
    }

    fun number(v: Double?): String {
        if (v == null) return "—"
        val a = kotlin.math.abs(v)
        return when {
            a >= 1e9 -> usFmt("%.1f mlrd", v / 1e9)
            a >= 1e6 -> usFmt("%.1f mln", v / 1e6)
            a >= 1e4 -> usFmt("%,.0f", v).replace(',', ' ')
            v == Math.floor(v) -> v.toLong().toString()
            else -> usFmt("%.2f", v)
        }
    }
}

/** Numbers with a dot and no grouping surprises, whatever the phone's language is. */
fun usFmt(pattern: String, vararg args: Any?): String = String.format(java.util.Locale.US, pattern, *args)
