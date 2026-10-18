package uz.nexvara.mobile.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import uz.nexvara.mobile.ThemeMode

/** NEXVARA brand: indigo #6366F1, cyan #06B6D4, night #0B1020 (same as the Windows app). */
object Brand {
    val Indigo = Color(0xFF6366F1)
    val IndigoDeep = Color(0xFF4F46E5)
    val Cyan = Color(0xFF06B6D4)
    val Night = Color(0xFF0B1020)
}

@Immutable
data class Extra(
    val success: Color, val warning: Color, val danger: Color, val info: Color,
    val card: Color, val cardBorder: Color, val muted: Color, val dark: Boolean,
)

val LocalExtra = staticCompositionLocalOf {
    Extra(Color.Green, Color.Yellow, Color.Red, Color.Cyan, Color.White, Color.LightGray, Color.Gray, false)
}

private val DarkColors = darkColorScheme(
    primary = Color(0xFF818CF8), onPrimary = Color(0xFF0B1020),
    primaryContainer = Color(0xFF262B66), onPrimaryContainer = Color(0xFFE0E3FF),
    secondary = Color(0xFF22D3EE), onSecondary = Color(0xFF00222A),
    secondaryContainer = Color(0xFF0D3A47), onSecondaryContainer = Color(0xFFC6F6FF),
    background = Brand.Night, onBackground = Color(0xFFE7EAF6),
    surface = Color(0xFF111833), onSurface = Color(0xFFE7EAF6),
    surfaceVariant = Color(0xFF1A2247), onSurfaceVariant = Color(0xFFA2AAD0),
    surfaceContainer = Color(0xFF141C3B), surfaceContainerHigh = Color(0xFF1A2247),
    surfaceContainerHighest = Color(0xFF212A55), surfaceContainerLow = Color(0xFF0F1630),
    outline = Color(0xFF39436E), outlineVariant = Color(0xFF263056),
    error = Color(0xFFF87171), onError = Color(0xFF2A0606),
)

private val LightColors = lightColorScheme(
    primary = Brand.IndigoDeep, onPrimary = Color.White,
    primaryContainer = Color(0xFFE3E4FF), onPrimaryContainer = Color(0xFF1E1B6B),
    secondary = Color(0xFF0891B2), onSecondary = Color.White,
    secondaryContainer = Color(0xFFD5F6FD), onSecondaryContainer = Color(0xFF053744),
    background = Color(0xFFF4F5FB), onBackground = Color(0xFF10142A),
    surface = Color.White, onSurface = Color(0xFF10142A),
    surfaceVariant = Color(0xFFEDEFF8), onSurfaceVariant = Color(0xFF5A6286),
    surfaceContainer = Color(0xFFF0F1F9), surfaceContainerHigh = Color(0xFFE9EBF6),
    surfaceContainerHighest = Color(0xFFE2E5F3), surfaceContainerLow = Color(0xFFF8F9FD),
    outline = Color(0xFFC9CEE6), outlineVariant = Color(0xFFE1E4F2),
    error = Color(0xFFDC2626), onError = Color.White,
)

private val AppTypography = Typography().run {
    copy(
        headlineMedium = headlineMedium.copy(fontWeight = FontWeight.Bold, fontSize = 26.sp, letterSpacing = (-0.3).sp),
        headlineSmall = headlineSmall.copy(fontWeight = FontWeight.Bold, fontSize = 22.sp),
        titleLarge = titleLarge.copy(fontWeight = FontWeight.SemiBold, fontSize = 20.sp),
        titleMedium = titleMedium.copy(fontWeight = FontWeight.SemiBold, fontSize = 16.sp),
        titleSmall = titleSmall.copy(fontWeight = FontWeight.SemiBold),
        labelLarge = labelLarge.copy(fontWeight = FontWeight.SemiBold, fontSize = 15.sp),
        bodyLarge = bodyLarge.copy(fontSize = 16.sp, lineHeight = 23.sp),
        bodyMedium = bodyMedium.copy(fontSize = 14.sp, lineHeight = 20.sp),
    )
}

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp), small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

val Numbers = TextStyle(fontWeight = FontWeight.Bold, fontSize = 24.sp, letterSpacing = (-0.5).sp)

@Composable
fun NexvaraTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.System -> isSystemInDarkTheme()
        ThemeMode.Light -> false
        ThemeMode.Dark -> true
    }
    val extra = if (dark) Extra(
        success = Color(0xFF34D399), warning = Color(0xFFFBBF24), danger = Color(0xFFF87171),
        info = Color(0xFF22D3EE), card = Color(0xFF131B3A), cardBorder = Color(0xFF232D58),
        muted = Color(0xFF8F98C2), dark = true,
    ) else Extra(
        success = Color(0xFF059669), warning = Color(0xFFB45309), danger = Color(0xFFDC2626),
        info = Color(0xFF0891B2), card = Color.White, cardBorder = Color(0xFFE3E6F3),
        muted = Color(0xFF68708F), dark = false,
    )
    // Status and navigation bar icons follow the app theme (dark icons on the light theme).
    val view = androidx.compose.ui.platform.LocalView.current
    if (!view.isInEditMode) androidx.compose.runtime.SideEffect {
        val window = (view.context as? android.app.Activity)?.window ?: return@SideEffect
        androidx.core.view.WindowCompat.getInsetsController(window, view).run {
            isAppearanceLightStatusBars = !dark
            isAppearanceLightNavigationBars = !dark
        }
    }
    CompositionLocalProvider(LocalExtra provides extra) {
        MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, typography = AppTypography,
            shapes = AppShapes, content = content)
    }
}
