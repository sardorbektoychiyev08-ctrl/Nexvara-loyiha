package uz.nexvara.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import uz.nexvara.mobile.Fmt

val Gutter = 16.dp

@Composable
fun Logo(size: Dp = 40.dp) {
    Box(
        Modifier.size(size).clip(RoundedCornerShape(size * 0.3f))
            .background(Brush.linearGradient(listOf(Brand.Indigo, Brand.Cyan))),
        contentAlignment = Alignment.Center,
    ) { Text("N", color = Color.White, fontWeight = FontWeight.Black, style = MaterialTheme.typography.titleLarge) }
}

/** The title row of a screen: back arrow (sub-screens), title, optional actions. */
@Composable
fun ScreenHeader(title: String, subtitle: String? = null, onBack: (() -> Unit)? = null,
                 actions: @Composable RowScope.() -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(start = if (onBack == null) Gutter else 4.dp, end = 8.dp, top = 10.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically) {
        if (onBack != null) IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Orqaga") }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.headlineSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (subtitle != null) Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = LocalExtra.current.muted,
                maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        actions()
    }
}

@Composable
fun Panel(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, padding: Dp = 16.dp,
          content: @Composable ColumnScope.() -> Unit) {
    val x = LocalExtra.current
    val shape = MaterialTheme.shapes.large
    Surface(
        modifier = modifier.fillMaxWidth().then(if (onClick != null) Modifier.clip(shape).clickable(onClick = onClick) else Modifier),
        shape = shape, color = x.card, border = BorderStroke(1.dp, x.cardBorder),
        shadowElevation = if (x.dark) 0.dp else 1.dp,
    ) { Column(Modifier.padding(padding), content = content) }
}

@Composable
fun SectionTitle(text: String, action: String? = null, onAction: (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(top = 18.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
        if (action != null && onAction != null) TextButton(onClick = onAction, contentPadding = PaddingValues(horizontal = 8.dp)) { Text(action) }
    }
}

@Composable
fun IconBadge(icon: ImageVector, tint: Color, size: Dp = 40.dp) {
    Box(Modifier.size(size).clip(RoundedCornerShape(size * 0.32f)).background(tint.copy(alpha = 0.14f)),
        contentAlignment = Alignment.Center) { Icon(icon, null, tint = tint, modifier = Modifier.size(size * 0.55f)) }
}

/** A tile in the sections grid and in quick actions. */
@Composable
fun Tile(icon: ImageVector, title: String, subtitle: String?, tint: Color, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Panel(modifier, onClick = onClick, padding = 14.dp) {
        IconBadge(icon, tint)
        Spacer(Modifier.height(12.dp))
        Text(title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
        if (subtitle != null) Text(subtitle, style = MaterialTheme.typography.bodySmall, color = LocalExtra.current.muted,
            maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun ListRow(icon: ImageVector?, title: String, subtitle: String? = null, tint: Color = MaterialTheme.colorScheme.primary,
            onClick: (() -> Unit)? = null, trailing: @Composable (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().then(if (onClick != null) Modifier.clip(MaterialTheme.shapes.medium).clickable(onClick = onClick) else Modifier)
        .padding(vertical = 10.dp, horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        if (icon != null) { IconBadge(icon, tint, 36.dp); Spacer(Modifier.width(12.dp)) }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (!subtitle.isNullOrBlank()) Text(subtitle, style = MaterialTheme.typography.bodySmall, color = LocalExtra.current.muted,
                maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
        trailing?.invoke()
    }
}

fun statusColor(status: String, x: Extra): Color = when (status) {
    "succeeded" -> x.success
    "failed" -> x.danger
    "cancelled" -> x.muted
    "paused" -> x.warning
    else -> x.info
}

fun statusIcon(status: String): ImageVector = when (status) {
    "succeeded" -> Icons.Default.CheckCircle
    "failed" -> Icons.Default.Error
    "cancelled" -> Icons.Default.Block
    "paused" -> Icons.Default.PauseCircle
    "pending" -> Icons.Default.Schedule
    else -> Icons.Default.Autorenew
}

@Composable
fun StatusPill(status: String, label: String = Fmt.status(status)) {
    val c = statusColor(status, LocalExtra.current)
    Row(Modifier.clip(CircleShape).background(c.copy(alpha = 0.14f)).padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Icon(statusIcon(status), null, tint = c, modifier = Modifier.size(14.dp))
        Spacer(Modifier.width(5.dp))
        Text(label, color = c, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun Dot(color: Color, size: Dp = 9.dp) { Box(Modifier.size(size).clip(CircleShape).background(color)) }

@Composable
fun EmptyState(icon: ImageVector, title: String, text: String, action: String? = null, onAction: (() -> Unit)? = null) {
    Column(Modifier.fillMaxWidth().padding(vertical = 36.dp, horizontal = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        IconBadge(icon, MaterialTheme.colorScheme.primary, 64.dp)
        Spacer(Modifier.height(14.dp))
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = LocalExtra.current.muted,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        if (action != null && onAction != null) { Spacer(Modifier.height(16.dp)); FilledTonalButton(onClick = onAction) { Text(action) } }
    }
}

/** Spent vs limit (green → amber → red). */
@Composable
fun LimitBar(spent: Double, limit: Double?) {
    val x = LocalExtra.current
    val f = if (limit == null || limit <= 0) 0f else (spent / limit).toFloat().coerceIn(0f, 1f)
    val c = when { f >= 1f -> x.danger; f >= 0.8f -> x.warning; else -> x.success }
    LinearProgressIndicator(progress = { f }, modifier = Modifier.fillMaxWidth().height(7.dp).clip(CircleShape),
        color = c, trackColor = MaterialTheme.colorScheme.surfaceVariant, drawStopIndicator = {})
}

@Composable
fun ConfirmDialog(title: String, text: String, yes: String, danger: Boolean = false, onYes: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = { Text(text) },
        confirmButton = {
            Button(onClick = { onYes(); onDismiss() }, colors = if (danger) ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.error, contentColor = MaterialTheme.colorScheme.onError) else ButtonDefaults.buttonColors()) { Text(yes) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Bekor qilish") } })
}

@Composable
fun TextInputDialog(title: String, initial: String = "", label: String, confirm: String = "Saqlash",
                    multiline: Boolean = false, onSave: (String) -> Unit, onDismiss: () -> Unit) {
    var text by remember { mutableStateOf(initial) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) },
        text = { OutlinedTextField(text, { text = it }, label = { Text(label) }, minLines = if (multiline) 3 else 1,
            modifier = Modifier.fillMaxWidth()) },
        confirmButton = { Button(onClick = { onSave(text.trim()); onDismiss() }, enabled = text.isNotBlank()) { Text(confirm) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Bekor qilish") } })
}

@Composable
fun ChipRow(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScrollSafe(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) ->
            FilterChip(selected = key == selected, onClick = { onSelect(key) }, label = { Text(label) })
        }
    }
}

@Composable
fun Modifier.horizontalScrollSafe(): Modifier = this.then(Modifier.horizontalScroll(androidx.compose.foundation.rememberScrollState()))
