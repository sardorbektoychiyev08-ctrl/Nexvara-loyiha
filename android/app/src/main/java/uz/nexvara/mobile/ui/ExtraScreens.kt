package uz.nexvara.mobile.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculatePan
import kotlinx.coroutines.delay
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import uz.nexvara.mobile.*

// ---------------- the PC screen, live; control mode taps on it ----------------
@Composable
fun PcScreenView(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    var box by remember { mutableStateOf(androidx.compose.ui.unit.IntSize.Zero) }
    val zoom = rememberTransformableState { z, pan, _ ->
        scale = (scale * z).coerceIn(1f, 5f)
        offset = if (scale == 1f) Offset.Zero else offset + pan
    }
    var cmd by rememberSaveable { mutableStateOf("") }
    var typing by remember { mutableStateOf(false) }
    val control = m.tools.controlOn
    val pad = control && m.tools.touchpad
    val move = remember { floatArrayOf(0f, 0f) }  // finger movement not sent yet, PC pixels
    LaunchedEffect(pad) {  // at most ~25 small moves a second, so the network keeps up
        while (pad) {
            delay(40)
            val dx = move[0].toInt().coerceIn(-800, 800)
            val dy = move[1].toInt().coerceIn(-800, 800)
            if (dx != 0 || dy != 0) { move[0] -= dx; move[1] -= dy; m.control("nudge", dx = dx, dy = dy) }
        }
    }
    /** A tap on the picture → 0..1 of the PC screen (undoing fit, zoom and pan). */
    fun toPc(p: Offset): Pair<Float, Float>? {
        val bmp = m.screenShot ?: return null
        if (box.width == 0) return null
        val cx = box.width / 2f
        val cy = box.height / 2f
        val ux = (p.x - cx - offset.x) / scale + cx
        val uy = (p.y - cy - offset.y) / scale + cy
        val fit = minOf(box.width.toFloat() / bmp.width, box.height.toFloat() / bmp.height)
        val w = bmp.width * fit
        val h = bmp.height * fit
        val nx = (ux - (box.width - w) / 2f) / w
        val ny = (uy - (box.height - h) / 2f) / h
        return if (nx in 0f..1f && ny in 0f..1f) nx to ny else null
    }
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Kompyuter ekrani", if (pad) "Sensorli panel" else if (control) "Boshqarish rejimi" else if (m.screenLive) "Jonli · ${m.screenInfo}" else "To‘xtatilgan",
            onBack = { stopControl(m); m.goBack() }) {
            IconButton(onClick = {
                if (control) stopControl(m)
                else act.confirm("Kompyuterni boshqarish") { m.tools.controlOn = true }
            }) { Icon(if (control) Icons.Default.TouchApp else Icons.Default.Mouse, "Boshqarish", tint = if (control) x.warning else LocalContentColor.current) }
            IconButton(onClick = { if (m.screenLive) m.stopScreen() else m.startScreen() }) {
                Icon(if (m.screenLive) Icons.Default.Pause else Icons.Default.PlayArrow, if (m.screenLive) "To‘xtatish" else "Davom ettirish")
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 8.dp).clip(RoundedCornerShape(14.dp))
            .background(Color(0xFF05070F)).onSizeChanged { box = it }
            .then(if (pad) Modifier else Modifier.transformable(zoom))
            .pointerInput(control, pad) {
                if (pad) awaitEachGesture {
                    // Touchpad: slide = move the pointer, tap = click, two taps = double click,
                    // hold = right click, two fingers up/down = scroll.
                    val down = awaitFirstDown()
                    val start = System.currentTimeMillis()
                    var path = 0f
                    var multi = false
                    var wheel = 0f
                    while (true) {
                        val ev = awaitPointerEvent()
                        val pressed = ev.changes.filter { it.pressed }
                        if (pressed.isEmpty()) break
                        if (pressed.size >= 2) {
                            multi = true
                            wheel += ev.calculatePan().y
                            val steps = (wheel / 45f).toInt()
                            if (steps != 0) { wheel -= steps * 45f; m.control("scroll", dy = steps) }
                        } else if (!multi) {
                            val c = pressed[0]
                            val d = c.position - c.previousPosition
                            val len = d.getDistance()
                            path += len
                            val speed = 1.3f + minOf(len / 18f, 2.2f)  // faster finger = farther
                            move[0] += d.x * speed; move[1] += d.y * speed
                        }
                        ev.changes.forEach { it.consume() }
                    }
                    if (!multi && path < 14f) {
                        m.control(if (System.currentTimeMillis() - start > 550) "tap_right" else "tap")
                    }
                    down.consume()
                } else if (control) detectTapGestures(
                    onTap = { p -> toPc(p)?.let { (a, b) -> m.control("click", a, b) } },
                    onDoubleTap = { p -> toPc(p)?.let { (a, b) -> m.control("double", a, b) } },
                    onLongPress = { p -> toPc(p)?.let { (a, b) -> m.control("right", a, b) } },
                )
            }, contentAlignment = Alignment.Center) {
            val bmp = m.screenShot
            if (bmp == null) Text("Kompyuter ekrani yuklanmoqda…", color = Color.White.copy(0.7f))
            else Image(bmp.asImageBitmap(), "Kompyuter ekrani", contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = scale, scaleY = scale,
                    translationX = offset.x, translationY = offset.y, alpha = if (pad) 0.55f else 1f))
            if (pad) Text("Sensorli panel", color = Color.White.copy(0.35f), style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 10.dp))
        }
        if (control) {
            Row(Modifier.fillMaxWidth().horizontalScrollSafe().padding(horizontal = 8.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                FilterChip(m.tools.touchpad, onClick = { m.tools.touchpad = !m.tools.touchpad },
                    label = { Text("Sensorli panel") }, leadingIcon = { Icon(Icons.Default.TouchApp, null) })
                if (pad) FilterChip(m.tools.dragging, onClick = {
                    m.tools.dragging = !m.tools.dragging
                    m.control(if (m.tools.dragging) "drag_start" else "drag_end")
                }, label = { Text(if (m.tools.dragging) "Qo‘yib yuborish" else "Ushlab sudrash") })
                AssistChip(onClick = { typing = true }, label = { Text("Yozish") }, leadingIcon = { Icon(Icons.Default.Keyboard, null) })
                AssistChip(onClick = { m.control("scroll", dy = 3) }, label = { Text("▲") })
                AssistChip(onClick = { m.control("scroll", dy = -3) }, label = { Text("▼") })
                listOf("enter" to "Enter", "esc" to "Esc", "tab" to "Tab", "backspace" to "⌫", "ctrl+z" to "Ctrl+Z",
                    "ctrl+c" to "Ctrl+C", "ctrl+v" to "Ctrl+V", "ctrl+s" to "Ctrl+S", "alt+tab" to "Alt+Tab", "win" to "Win")
                    .forEach { (k, label) -> AssistChip(onClick = { m.control("key", key = k) }, label = { Text(label) }) }
            }
            Text(if (pad) "Barmoqni suring — kursor yuradi. Bosish — chap tugma, ikki marta — ochish, uzoq bosish — o‘ng tugma, " +
                    "ikki barmoq bilan yuqoriga/pastga — aylantirish. Kompyuterda «📱 Telefon boshqarmoqda» chiqadi."
                else "Ekrandagi joyga bosing — o‘sha joy bosiladi. Ikki marta — ochish, uzoq bosish — o‘ng tugma. Kompyuterda «📱 Telefon boshqarmoqda» chiqadi.",
                style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(horizontal = Gutter))
        } else {
            Text("Ko‘rish rejimi. Boshqarish uchun yuqoridagi sichqoncha belgisini bosing (kompyuterda ruxsat yoqilgan bo‘lishi kerak).",
                style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(horizontal = Gutter, vertical = 6.dp))
        }
        Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(cmd, { cmd = it }, modifier = Modifier.weight(1f), placeholder = { Text("NEXVARA’ga buyruq…") },
                maxLines = 3, shape = RoundedCornerShape(22.dp))
            Spacer(Modifier.width(6.dp))
            FilledIconButton(onClick = { m.send(cmd); cmd = "" }, enabled = cmd.isNotBlank(), modifier = Modifier.size(48.dp)) {
                Icon(Icons.AutoMirrored.Filled.Send, "Yuborish")
            }
        }
    }
    if (typing) TextInputDialog("Kompyuterga yozish", label = "Matn (kursor turgan joyga yoziladi)", confirm = "Yozish", multiline = true,
        onSave = { m.control("type", text = it) }, onDismiss = { typing = false })
}

/** Leaving control mode never leaves the PC's left button held down. */
private fun stopControl(m: AppModel) {
    if (m.tools.dragging) { m.tools.dragging = false; m.control("drag_end") }
    m.tools.controlOn = false
}

// ---------------- ready commands for teachers, office work, documents ----------------
private data class Ready(val title: String, val text: String)

private val READY: List<Triple<String, androidx.compose.ui.graphics.vector.ImageVector, List<Ready>>> = listOf(
    Triple("O‘qituvchi uchun", Icons.Default.School, listOf(
        Ready("Darslikdan test (bepul)", "7-sinf fizika «Nyuton qonunlari» mavzusidan 20 ta test, 2 variant"),
        Ready("Mavzu matni darslikdan", "7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber"),
        Ready("Mavzu bo‘yicha taqdimot", "7-sinf fizika Nyuton qonunlari bo‘yicha taqdimot tayyorla"),
        Ready("AI bilan test", "AI bilan 7-sinf fizika «Nyuton qonunlari» mavzusidan 15 ta test tuz"),
        Ready("Dars rejasi (AI)", "AI bilan 7-sinf fizika «Nyuton qonunlari» uchun 45 daqiqalik dars rejasi tuz"),
        Ready("Uyga vazifa va javoblar (AI)", "AI bilan 5-sinf matematika «Kasrlar» bo‘yicha uyga vazifa va javoblarini tuz"),
        Ready("Ota-onalarga e’lon (AI)", "AI bilan ota-onalar yig‘ilishi haqida qisqa e’lon matnini yoz"),
        Ready("Baholar jadvali", "Baholar.xlsx ni och, jadvalni formatla, B ustun bo‘yicha saralab, PDF qilib saqla"),
        Ready("Baholar dashboardi", "Baholar.xlsx dan dashboard qil"),
        Ready("Darslikdan savol (AI)", "AI bilan 7-sinf fizika darsligidan: inersiya nima?"),
    )),
    Triple("Ofis ishlari", Icons.Default.Work, listOf(
        Ready("Excel hisobotni tozalash", "Hisobot.xlsx ni och, dublikatlarni o‘chir, jadvalni formatla, jami qo‘sh, diagramma qo‘sh, PDF qilib saqla"),
        Ready("Saralash", "Savdo.xlsx ni summa bo‘yicha kamayish tartibida sartirovka qil"),
        Ready("Excel: hisob-kitob", "Savdo.xlsx ni och, Foyda = Daromad - Xarajat ustunini qo‘sh, jami qo‘sh, o‘rtacha qatorini qo‘sh, Daromad ustunini pul formatiga o‘tkaz va saqla"),
        Ready("Excel: rang bilan belgilash", "Savdo.xlsx da Summa 1000000 dan katta kataklarni qizil bilan belgila"),
        Ready("Excel: chop etishga tayyorlash", "Savdo.xlsx ni albom qilib bir sahifaga sig‘dir, ustunlar kengligini moslashtir va PDF qilib saqla"),
        Ready("Word: rasmiy hujjat", "Xat.docx ni och, ortiqcha bo‘sh joylarni tozala, hujjatni rasmiy formatla, sahifa raqamlarini qo‘y va PDF qilib saqla"),
        Ready("Word: kolontitul", "Xat.docx ga yuqori kolontitulga «5-maktab» yoz"),
        Ready("PowerPoint: tayyorlash", "Taqdimot.pptx ga barcha slaydlarga o‘tish effekti qo‘sh, slayd raqamlarini qo‘sh, slaydlarni tekshir va PDF qilib saqla"),
        Ready("Savdo dashboardi", "Savdo.xlsx dan dashboard qil"),
        Ready("Word’ni PDF qilish", "Xat.docx ni och, sahifa raqamini qo‘y, PDF qilib saqla"),
        Ready("Shu faylni PDF qilish", "Shu faylni PDF qilib saqla"),
        Ready("Fayl topish", "Hisobot fayllarini top"),
        Ready("Fonda bajarish", "Hisobot.xlsx ni och, jadvalni formatla, fonda bajar"),
    )),
    Triple("Hujjatlar (AI)", Icons.Default.Description, listOf(
        Ready("Ariza", "AI bilan ariza yoz: 3 kunlik ta’til so‘rab, maktab direktori nomiga"),
        Ready("Rasmiy xat", "AI bilan rasmiy xat yoz: hamkor tashkilotga uchrashuv taklifi"),
        Ready("Buyruq loyihasi", "AI bilan buyruq loyihasi tuz: ish vaqtini o‘zgartirish haqida"),
        Ready("Tarjima", "AI bilan quyidagi matnni rus tiliga tarjima qil: "),
        Ready("Qisqartirish", "AI bilan shu matnni qisqa xulosa qil: "),
    )),
    Triple("Chizma", Icons.Default.Architecture, listOf(
        Ready("Flanes (AI’siz, bepul)", "Diametri 80 mm flanes, markazda 30 mm teshik, 4 ta 8 mm boltli teshik — chizmasini chizib ber"),
        Ready("Plastina (AI’siz)", "120x80 plastina, burchaklarida 4 ta 10 mm teshik, burchaklari R8 yumaloq — chizib ber"),
        Ready("Shayba (AI’siz)", "Shayba chiz: tashqi diametri 40, ichki diametri 21"),
        Ready("Gayka (AI’siz)", "M12 gayka chizmasi, kalit 19 — chizib ber"),
        Ready("AutoCAD faylini ko‘rish", "Chizma.dxf ni PDF qil"),
        Ready("Sxema", "Elektr zanjiri sxemasini chizib ber: batareya, kalit, 2 ta lampa ketma-ket"),
        Ready("Oxirgi chizmani tuzatish", "Oxirgi chizmani o‘zgartir: "),
    )),
    Triple("Xotira va boshqalar", Icons.Default.Bookmarks, listOf(
        Ready("Eslab qolish", "Eslab qol: "),
        Ready("Nimalarni bilasan", "Nimalarni eslab qolding?"),
        Ready("Teach qoidasi", "Har doim Excel jadvalini formatla va jami qo‘sh"),
        Ready("Sinxronlash", "sinxronla"),
        Ready("Ish jarayonlari", "Ish jarayonlarini ko‘rsat"),
    )),
)

@Composable
fun TemplatesScreen(m: AppModel) {
    val x = LocalExtra.current
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Tayyor buyruqlar", "Bosing — suhbatda tahrirlab yuborasiz", onBack = { m.goBack() })
        LazyColumn(contentPadding = PaddingValues(start = Gutter, end = Gutter, bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (m.favorites.isNotEmpty()) {
                item { SectionTitle("★ Sevimlilar") }
                items(m.favorites) { f ->
                    Panel(onClick = { m.compose(f) }, padding = 12.dp) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(f, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            IconButton(onClick = { m.toggleFavorite(f) }) { Icon(Icons.Default.Star, "Olib tashlash", tint = x.warning) }
                        }
                    }
                }
            }
            val recent = m.recentCommands.filter { it !in m.favorites }.take(6)
            if (recent.isNotEmpty()) {
                item { SectionTitle("Oxirgi buyruqlar") }
                items(recent) { r ->
                    Panel(onClick = { m.compose(r) }, padding = 12.dp) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(r, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            IconButton(onClick = { m.toggleFavorite(r) }) { Icon(Icons.Default.StarBorder, "Sevimlilarga") }
                        }
                    }
                }
            }
            READY.forEach { (group, icon, list) ->
                item {
                    Row(Modifier.padding(top = 14.dp, bottom = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(icon, null, tint = MaterialTheme.colorScheme.primary); Spacer(Modifier.width(8.dp))
                        Text(group, style = MaterialTheme.typography.titleMedium)
                    }
                }
                items(list) { r ->
                    Panel(onClick = { m.compose(r.text) }, padding = 12.dp) {
                        Text(r.title, style = MaterialTheme.typography.titleSmall)
                        Text(r.text, style = MaterialTheme.typography.bodySmall, color = x.muted, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
            item {
                Text("«AI bilan» boshlanganlari pullik: avval narx so‘raladi. Qolganlari bepul, kompyuterning o‘zida bajariladi.",
                    style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(top = 10.dp))
            }
        }
    }
}

// ---------------- PC files: search, open on the PC, take to the phone ----------------
@Composable
fun PcFilesPanel(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    var q by rememberSaveable { mutableStateOf("") }
    var ext by rememberSaveable { mutableStateOf("") }
    val picked = remember { mutableStateListOf<String>() }
    var zip by remember { mutableStateOf<String?>(null) }
    Panel {
        Text("Kompyuterdan qidirish", style = MaterialTheme.typography.titleMedium)
        Text("Hujjatlar, Ish stoli, Yuklanmalar va OneDrive’dan nomi bo‘yicha", style = MaterialTheme.typography.bodySmall, color = x.muted)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(q, { q = it }, modifier = Modifier.fillMaxWidth(), singleLine = true, placeholder = { Text("masalan: hisobot") },
            leadingIcon = { Icon(Icons.Default.Search, null) },
            trailingIcon = { if (q.isNotBlank()) IconButton(onClick = { m.searchPc(q, ext) }) { Icon(Icons.Default.Done, "Qidirish") } })
        Spacer(Modifier.height(6.dp))
        ChipRow(listOf("" to "Hammasi", ".xlsx .xls .csv" to "Excel", ".docx .doc" to "Word", ".pptx" to "PowerPoint", ".pdf" to "PDF",
            ".jpg .png" to "Rasm", ".zip" to "ZIP"), ext) { ext = it; if (q.isNotBlank()) m.searchPc(q, it) }
        picked.retainAll(m.pcFiles.map { it.path }.toSet())
        if (m.pcFiles.isNotEmpty()) {
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(if (picked.isEmpty()) "ZIP uchun fayllarni belgilang" else "Belgilandi: ${picked.size} ta",
                    style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.weight(1f))
                FilledTonalButton(onClick = { m.zipOnPc(picked.toList()) { zip = it }; picked.clear() }, enabled = picked.isNotEmpty()) {
                    Icon(Icons.Default.FolderZip, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("ZIP qilish")
                }
            }
        }
        zip?.let { z ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("«${TransferChecks.resultFileName(z)}» tayyor", style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                TextButton(onClick = { act.saveResult(z) }) { Icon(Icons.Default.Download, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Telefonga") }
            }
        }
        m.pcFiles.take(40).forEach { f ->
            HorizontalDivider(Modifier.padding(vertical = 6.dp), color = x.cardBorder)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(f.path in picked, { on -> if (on) picked.add(f.path) else picked.remove(f.path) })
                Text(f.name, style = MaterialTheme.typography.bodyLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            Text("${f.folder} · ${Fmt.size(f.size)} · ${Fmt.ago(f.modified)}", style = MaterialTheme.typography.bodySmall, color = x.muted,
                maxLines = 1, overflow = TextOverflow.Ellipsis)
            Row(Modifier.fillMaxWidth().horizontalScrollSafe(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { m.openOnPc(f) }) { Icon(Icons.Default.DesktopWindows, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Kompyuterda ochish") }
                TextButton(onClick = { m.shareToPhone(f) { act.saveResult(it) } }) {
                    Icon(Icons.Default.Download, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Telefonga")
                }
                if (f.name.endsWith(".zip", ignoreCase = true)) TextButton(onClick = { m.unzipOnPc(f) }) { Text("Chiqarish") }
                else TextButton(onClick = { m.compose("«${f.path}» ni och, ") }) { Text("Buyruq") }
            }
        }
    }
}

// ---------------- other networks (Tailscale) ----------------
@Composable
fun NetworkCard(m: AppModel, act: PhoneActions) {
    val x = LocalExtra.current
    val tail = m.knownHosts.any { WindowsApi.isTailnet(it) }
    Panel {
        ListRow(if (m.route == "tailscale") Icons.Default.Public else Icons.Default.Wifi,
            when (m.route) { "tailscale" -> "Hozir: Tailscale orqali (boshqa tarmoq)"; "lan" -> "Hozir: bir xil Wi-Fi orqali"; else -> "Ulanish tekshirilmoqda" },
            if (tail) "Kompyuterning Tailscale manzili saqlangan — istalgan Wi-Fi yoki mobil internetdan ishlaydi"
            else "Boshqa Wi-Fi yoki mobil internetdan ishlash uchun Tailscale’ni sozlang", if (tail) x.success else Brand.Cyan)
        if (!tail) {
            Text("1. Kompyuterga va telefonga Tailscale’ni o‘rnating (bepul).\n2. Ikkalasida bitta hisob bilan kiring.\n" +
                "3. Telefon kompyuterga bir marta uy Wi-Fi’da ulansin — manzil o‘zi saqlanadi.",
                style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalButton(onClick = { act.openUrl("https://play.google.com/store/apps/details?id=com.tailscale.ipn") }) { Text("Telefonga o‘rnatish") }
                OutlinedButton(onClick = { act.openUrl("https://tailscale.com/download/windows") }) { Text("Kompyuter uchun") }
            }
        }
        Text("Xavfsizlik: Tailscale shifrlangan shaxsiy tarmoq (WireGuard); ustidan NEXVARA sertifikat izi va token ham tekshiriladi. " +
            "Router’da port ochish kerak emas; internetdan to‘g‘ridan-to‘g‘ri kelgan so‘rovni kompyuter rad etadi.",
            style = MaterialTheme.typography.bodySmall, color = x.muted, modifier = Modifier.padding(top = 6.dp))
    }
}
