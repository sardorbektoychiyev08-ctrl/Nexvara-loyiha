package uz.nexvara.mobile

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/** "Tayyor: …" notifications, shown once per task (the app and the background check share it). */
object Notifier {
    private const val CHANNEL = "tasks"

    fun channel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel(CHANNEL, "Vazifalar", NotificationManager.IMPORTANCE_DEFAULT)
            ch.description = "Kompyuterdagi vazifa tugaganda xabar"
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }

    @Synchronized fun taskDone(ctx: Context, t: TaskItem) {
        val prefs = ctx.getSharedPreferences("nexvara_ui", Context.MODE_PRIVATE)
        val seen = prefs.getString("notified", "").orEmpty().split(',').filter { it.isNotBlank() }
        if (t.id in seen) return
        prefs.edit().putString("notified", (seen.takeLast(60) + t.id).joinToString(",")).apply()
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val open = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE)
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(if (t.status == "succeeded") "Tayyor: ${t.title}" else "${Fmt.status(t.status)}: ${t.title}")
            .setContentText(if (t.files.isNotEmpty()) "Natijani telefonga olish mumkin" else t.error.ifBlank { "NEXVARA" })
            .setContentIntent(open).setAutoCancel(true).build()
        try { NotificationManagerCompat.from(ctx).notify(t.id.hashCode(), n) } catch (_: SecurityException) { }
    }

    /** Every 15 minutes (Android's minimum) while the app is closed: finished tasks → a notification. */
    fun schedule(ctx: Context, on: Boolean) {
        val wm = WorkManager.getInstance(ctx)
        if (!on) { wm.cancelUniqueWork("nexvara-tasks"); return }
        val req = PeriodicWorkRequestBuilder<TaskCheckWorker>(15, TimeUnit.MINUTES).build()
        wm.enqueueUniquePeriodicWork("nexvara-tasks", ExistingPeriodicWorkPolicy.KEEP, req)
    }
}

class TaskCheckWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val ctx = applicationContext
        val prefs = ctx.getSharedPreferences("nexvara_ui", Context.MODE_PRIVATE)
        if (!prefs.getBoolean("bg_alerts", true)) return@withContext Result.success()
        val p = SecureSession(ctx).read() ?: return@withContext Result.success()
        val since = prefs.getLong("bg_since_ms", System.currentTimeMillis() - 3_600_000) / 1000.0
        try {
            val hosts = p.optJSONArray("hosts")?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty()
            val api = WindowsApi(PairCode.parse(p.getString("qr")), p.getString("token"), hosts)
            val tasks = Parse.tasks(api.json("/api/v1/tasks?limit=15").optJSONArray("tasks"))
            tasks.filter { !it.active && (it.finishedAt ?: 0.0) > since }.forEach { Notifier.taskDone(ctx, it) }
            prefs.edit().putLong("bg_since_ms", System.currentTimeMillis()).apply()
        } catch (_: Exception) {
            // The PC is off or on another network: try again next time, quietly.
        }
        Result.success()
    }
}
