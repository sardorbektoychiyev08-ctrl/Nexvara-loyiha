package uz.nexvara.mobile

import android.Manifest
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.widget.RemoteViews
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.Calendar

/** "3-dars 5 daqiqadan keyin": the next lesson's reminder (inexact alarm, no special permission). */
object Reminders {
    private const val CHANNEL = "lessons"

    fun schedule(ctx: Context) {
        val s = Schedule(ctx)
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        val pi = PendingIntent.getBroadcast(ctx, 7, Intent(ctx, ReminderReceiver::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        am.cancel(pi)
        val next = nextLesson(s.lessons, s.remindMinutes, System.currentTimeMillis()) ?: return
        am.setWindow(AlarmManager.RTC_WAKEUP, next.second, 60_000, pi)
    }

    /** (lesson, time to remind in millis) of the soonest reminder after [now]. */
    fun nextLesson(lessons: List<Lesson>, minutes: Int, now: Long): Pair<Lesson, Long>? {
        var best: Pair<Lesson, Long>? = null
        for (l in lessons) {
            val (h, m) = l.start.split(":").map { it.toInt() }
            for (week in 0..1) {
                val c = Calendar.getInstance().apply {
                    timeInMillis = now
                    set(Calendar.HOUR_OF_DAY, h); set(Calendar.MINUTE, m); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
                    val today = (get(Calendar.DAY_OF_WEEK) + 5) % 7
                    add(Calendar.DAY_OF_YEAR, (l.day - today + 7) % 7 + 7 * week)
                    add(Calendar.MINUTE, -minutes)
                }
                if (c.timeInMillis > now && (best == null || c.timeInMillis < best.second)) {
                    best = l to c.timeInMillis
                    break
                }
            }
        }
        return best
    }

    fun notifyLesson(ctx: Context, l: Lesson, minutes: Int) {
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.getSystemService(NotificationManager::class.java)
                .createNotificationChannel(NotificationChannel(CHANNEL, "Dars eslatmalari", NotificationManager.IMPORTANCE_HIGH))
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle("$minutes daqiqadan keyin: ${l.title}")
            .setContentText("${l.start}${if (l.room.isNotBlank()) " · ${l.room}" else ""}")
            .setContentIntent(PendingIntent.getActivity(ctx, 8, Intent(ctx, MainActivity::class.java)
                .putExtra("open", Screen.Schedule.name), PendingIntent.FLAG_IMMUTABLE))
            .setAutoCancel(true).build()
        try { NotificationManagerCompat.from(ctx).notify(l.id.hashCode(), n) } catch (_: SecurityException) { }
    }
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) { Reminders.schedule(ctx); Morning.schedule(ctx); return }
        val s = Schedule(ctx)
        Reminders.nextLesson(s.lessons, s.remindMinutes, System.currentTimeMillis() - 5 * 60_000)?.let { (l, _) ->
            Reminders.notifyLesson(ctx, l, s.remindMinutes)
        }
        Reminders.schedule(ctx)
    }
}

/** Wake-on-LAN: the "magic packet" (6 × FF + 16 × MAC) to the local broadcast address. */
object Wake {
    fun send(mac: String, broadcast: String) {
        val bytes = mac.split(':', '-').map { it.toInt(16).toByte() }
        require(bytes.size == 6) { "MAC manzil noto‘g‘ri" }
        val packet = ByteArray(6) { 0xFF.toByte() } + List(16) { bytes }.flatten()
        DatagramSocket().use { s ->
            s.broadcast = true
            for (target in listOf(broadcast, "255.255.255.255").distinct()) {
                for (port in listOf(9, 7)) {
                    s.send(DatagramPacket(packet, packet.size, InetAddress.getByName(target), port))
                }
            }
        }
    }
}

/** Home-screen widget: four big buttons straight into NEXVARA. */
class NexvaraWidget : AppWidgetProvider() {
    override fun onUpdate(ctx: Context, manager: AppWidgetManager, ids: IntArray) {
        val views = RemoteViews(ctx.packageName, R.layout.widget_nexvara)
        listOf(R.id.w_chat to Screen.Chat, R.id.w_test to Screen.Library, R.id.w_screen to Screen.PcScreen,
            R.id.w_file to Screen.Files).forEachIndexed { i, (id, screen) ->
            val pi = PendingIntent.getActivity(ctx, 100 + i, Intent(ctx, MainActivity::class.java)
                .putExtra("open", screen.name).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            views.setOnClickPendingIntent(id, pi)
        }
        manager.updateAppWidget(ids, views)
    }

    companion object {
        fun refresh(ctx: Context) {
            val m = AppWidgetManager.getInstance(ctx)
            val ids = m.getAppWidgetIds(ComponentName(ctx, NexvaraWidget::class.java))
            if (ids.isNotEmpty()) NexvaraWidget().onUpdate(ctx, m, ids)
        }
    }
}
