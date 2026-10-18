package uz.nexvara.mobile

import android.Manifest
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.util.Calendar

/**
 * «Xayrli tong»: every morning at the chosen time a notification with today's lessons (from the
 * phone's own timetable) and what is waiting on the PC (failed tasks, «Ha» to give, today's
 * automatic jobs, an old backup). The PC part is skipped quietly when the PC is off.
 */
object Morning {
    private const val CHANNEL = "morning"
    private const val PREFS = "nexvara_ui"

    fun enabled(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("morning_on", true)
    fun time(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("morning_time", "07:30") ?: "07:30"

    fun set(ctx: Context, on: Boolean, time: String) {
        require(time.matches(Regex("([01]?\\d|2[0-3]):[0-5]\\d"))) { "Vaqt HH:MM bo‘lsin" }
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("morning_on", on).putString("morning_time", time).apply()
        schedule(ctx)
    }

    private fun pending(ctx: Context) = PendingIntent.getBroadcast(ctx, 9, Intent(ctx, MorningReceiver::class.java),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    fun schedule(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        val pi = pending(ctx)
        am.cancel(pi)
        if (!enabled(ctx)) return
        am.setWindow(AlarmManager.RTC_WAKEUP, next(time(ctx), System.currentTimeMillis()), 5 * 60_000, pi)
    }

    /** The next HH:MM after [now] (today or tomorrow). */
    fun next(hhmm: String, now: Long): Long {
        val (h, m) = hhmm.split(":").map { it.toInt() }
        val c = Calendar.getInstance().apply {
            timeInMillis = now
            set(Calendar.HOUR_OF_DAY, h); set(Calendar.MINUTE, m); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
        }
        if (c.timeInMillis <= now) c.add(Calendar.DAY_OF_YEAR, 1)
        return c.timeInMillis
    }

    /** Title and lines of the notification (pure, unit-tested). */
    fun text(weekday: String, lessons: List<Lesson>, pcLines: List<String>?, pcOff: Boolean): Pair<String, List<String>> {
        val out = mutableListOf<String>()
        if (lessons.isEmpty()) out += "📚 Bugun jadvalda dars yo‘q"
        else {
            out += "📚 Bugun ${lessons.size} ta dars:"
            lessons.sortedBy { it.start }.forEach { out += "   ${it.start} ${it.title}${if (it.room.isNotBlank()) " (${it.room})" else ""}" }
        }
        when {
            pcLines == null && pcOff -> out += "💻 Kompyuter o‘chiq yoki boshqa tarmoqda"
            pcLines.isNullOrEmpty() -> out += "💻 Kompyuterda kutayotgan ish yo‘q"
            else -> out += pcLines
        }
        return "Xayrli tong! Bugun $weekday" to out
    }

    fun notify(ctx: Context, title: String, lines: List<String>) {
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.getSystemService(NotificationManager::class.java)
                .createNotificationChannel(NotificationChannel(CHANNEL, "Ertalabki xulosa", NotificationManager.IMPORTANCE_DEFAULT))
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_today)
            .setContentTitle(title)
            .setContentText(lines.firstOrNull().orEmpty())
            .setStyle(NotificationCompat.BigTextStyle().bigText(lines.joinToString("\n")))
            .setContentIntent(PendingIntent.getActivity(ctx, 10, Intent(ctx, MainActivity::class.java)
                .putExtra("open", Screen.Schedule.name), PendingIntent.FLAG_IMMUTABLE))
            .setAutoCancel(true).build()
        try { NotificationManagerCompat.from(ctx).notify(7301, n) } catch (_: SecurityException) { }
    }

    /** Builds and shows the summary now (also the «Hozir ko‘rsat» button). Blocking: call off the UI thread. */
    fun show(ctx: Context) {
        val lessons = Schedule(ctx).today()
        var pc: List<String>? = null
        var off = false
        val p = SecureSession(ctx).read()
        if (p != null) {
            try {
                val hosts = p.optJSONArray("hosts")?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty()
                val api = WindowsApi(PairCode.parse(p.getString("qr")), p.getString("token"), hosts)
                val d = api.json("/api/v1/morning")
                val a = d.optJSONArray("lines")
                pc = (0 until (a?.length() ?: 0)).map { a!!.optString(it) }
            } catch (_: Exception) {
                off = true
            }
        }
        val (title, lines) = text(Schedule.DAYS[Schedule.todayIndex()], lessons, pc, off)
        notify(ctx, title, lines)
    }
}

class MorningReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val done = goAsync()
        Thread {
            try { Morning.show(ctx) } catch (_: Exception) { } finally {
                Morning.schedule(ctx)  // tomorrow
                done.finish()
            }
        }.start()
    }
}
