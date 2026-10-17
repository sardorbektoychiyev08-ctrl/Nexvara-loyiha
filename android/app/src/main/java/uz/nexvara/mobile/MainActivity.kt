package uz.nexvara.mobile

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialException
import androidx.lifecycle.viewModelScope
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.launch
import uz.nexvara.mobile.ui.AppRoot
import uz.nexvara.mobile.ui.BuildConfigInfo
import uz.nexvara.mobile.ui.NexvaraTheme
import uz.nexvara.mobile.ui.PhoneActions
import java.util.Locale
import java.util.UUID

class MainActivity : FragmentActivity() {
    private val model: AppModel by viewModels()
    private var tts: TextToSpeech? = null
    private var ttsReady by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        BuildConfigInfo.version = runCatching { packageManager.getPackageInfo(packageName, 0).versionName }.getOrNull().orEmpty()
        Notifier.channel(this)
        Notifier.schedule(this, model.backgroundAlerts)
        model.onReply = { text -> if (model.speakReplies) speak(text) }
        model.onTaskDone = { t -> if (model.background) Notifier.taskDone(this, t) }
        handleShare(intent)
        setContent {
            var cameraUri by rememberSaveable { mutableStateOf<String?>(null) }
            var pendingSave by rememberSaveable { mutableStateOf<String?>(null) }
            val scanner = rememberLauncherForActivityResult(ScanContract()) { r -> r.contents?.let { model.connect(it) } }
            val pick = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { it?.let(model::upload) }
            val takePicture = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
                val photo = cameraUri
                cameraUri = null
                if (ok && photo != null) model.upload(Uri.parse(photo))
            }
            fun launchCamera() {
                val folder = java.io.File(cacheDir, "camera").apply { mkdirs() }
                val file = java.io.File(folder, "rasm-${System.currentTimeMillis()}.jpg")
                val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
                cameraUri = uri.toString()
                takePicture.launch(uri)
            }
            val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
                if (granted) launchCamera() else model.notice = "Kamera ruxsati berilmadi"
            }
            val save = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("*/*")) { uri ->
                val path = pendingSave
                pendingSave = null
                if (uri != null && path != null) model.download(path, uri)
            }
            val speech = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
                r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { model.dictated = it }
            }
            val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
            val actions = PhoneActions(
                scanQr = {
                    scanner.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                        .setPrompt("NEXVARA QR kodini skanerlang").setBeepEnabled(false).setOrientationLocked(false))
                },
                pickFile = { pick.launch("*/*") },
                pickImage = { pick.launch("image/*") },
                pickPdf = { pick.launch("application/pdf") },
                takePhoto = {
                    if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchCamera()
                    else cameraPermission.launch(Manifest.permission.CAMERA)
                },
                listen = {
                    stopSpeaking()
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "uz-UZ")
                        .putExtra(RecognizerIntent.EXTRA_PROMPT, "Buyruqni ayting")
                    try { speech.launch(intent) } catch (_: Exception) { model.notice = "Telefonda ovozni tanish xizmati yo‘q" }
                },
                saveResult = { path ->
                    pendingSave = path
                    save.launch(TransferChecks.resultFileName(path))
                },
                openUrl = { url ->
                    if (url.startsWith("https://")) runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                        .onFailure { model.notice = "Brauzer ochilmadi" }
                },
                googleSignIn = ::googleSignIn,
                stopSpeaking = ::stopSpeaking,
                unlock = ::unlock,
            )
            // Asked once, after the first pairing; a launcher may only be used after composition.
            androidx.compose.runtime.LaunchedEffect(model.profile != null) {
                if (Build.VERSION.SDK_INT >= 33 && model.profile != null &&
                    ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
                    !model.secure.flag("asked_notifications")) {
                    model.secure.setFlag("asked_notifications")
                    notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
            }
            androidx.compose.runtime.LaunchedEffect(model.secureScreen) {
                if (model.secureScreen) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
                else window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
            }
            androidx.compose.runtime.LaunchedEffect(model.backgroundAlerts) { Notifier.schedule(this@MainActivity, model.backgroundAlerts) }
            NexvaraTheme(model.themeMode) { AppRoot(model, actions) }
        }
    }

    override fun onStart() {
        super.onStart()
        model.background = false
        model.cameForeground()
        if (model.profile != null) model.refreshAll()
    }
    override fun onStop() { model.background = true; model.wentBackground(); super.onStop() }

    // ---------------- app lock (fingerprint / face / the phone's PIN) ----------------
    private fun unlock() {
        val strong = BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        val info = BiometricPrompt.PromptInfo.Builder().setTitle("NEXVARA").setSubtitle("Ilovani ochish uchun tasdiqlang")
        if (Build.VERSION.SDK_INT >= 30) info.setAllowedAuthenticators(strong)
        else @Suppress("DEPRECATION") info.setDeviceCredentialAllowed(true)
        val ok = BiometricManager.from(this).canAuthenticate(if (Build.VERSION.SDK_INT >= 30) strong
            else BiometricManager.Authenticators.BIOMETRIC_WEAK)
        if (ok == BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED || ok == BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE) {
            val km = getSystemService(android.app.KeyguardManager::class.java)
            if (km?.isDeviceSecure != true) { model.locked = false; model.setLock(false); model.notice = "Telefonda ekran qulfi yo‘q — ilova qulfi o‘chirildi"; return }
        }
        BiometricPrompt(this, ContextCompat.getMainExecutor(this), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) { model.locked = false }
            override fun onAuthenticationError(code: Int, msg: CharSequence) {
                if (code != BiometricPrompt.ERROR_USER_CANCELED && code != BiometricPrompt.ERROR_NEGATIVE_BUTTON) model.notice = msg.toString()
            }
        }).authenticate(info.build())
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    /** "Ulashish → NEXVARA" from any app: files go to the PC, text goes into the chat box. */
    private fun handleShare(intent: Intent?) {
        if (intent == null || model.profile == null) return
        val uris: List<Uri> = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(
                if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_STREAM))
            Intent.ACTION_SEND_MULTIPLE -> (if (Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)).orEmpty()
            else -> return
        }
        uris.take(10).forEach { model.upload(it) }
        if (uris.isNotEmpty()) model.open(Screen.Chat)
        else intent.getStringExtra(Intent.EXTRA_TEXT)?.let { model.compose(it.take(4000)) }
        intent.action = null  // handled once
    }

    override fun onDestroy() { tts?.shutdown(); tts = null; super.onDestroy() }

    // ---------------- voice replies (the phone's own TTS: free, offline when the voice is installed) ----------------
    private fun speak(text: String) {
        val clean = text.replace(Regex("[•⟦⟧*#_`]"), " ").take(600)
        val engine = tts
        if (engine != null && ttsReady) { engine.speak(clean, TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString()); return }
        tts = TextToSpeech(this) { status ->
            if (status != TextToSpeech.SUCCESS) { model.notice = "Ovoz bilan o‘qish xizmati yo‘q"; return@TextToSpeech }
            val t = tts ?: return@TextToSpeech
            val lang = listOf(Locale("uz", "UZ"), Locale("uz"), Locale("tr", "TR")).firstOrNull {
                t.isLanguageAvailable(it) >= TextToSpeech.LANG_AVAILABLE
            }
            if (lang != null) t.language = lang else model.notice = "Telefonda o‘zbekcha ovoz o‘rnatilmagan — standart ovoz ishlatiladi"
            ttsReady = true
            t.speak(clean, TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString())
        }
    }

    private fun stopSpeaking() { tts?.stop() }

    // ---------------- Google (Android Credential Manager; the PC verifies the token) ----------------
    private fun googleSignIn(webClientId: String) {
        model.viewModelScope.launch {
            try {
                val option = GetSignInWithGoogleOption.Builder(webClientId).build()
                val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
                val cred = CredentialManager.create(this@MainActivity).getCredential(this@MainActivity, request).credential
                if (cred is CustomCredential && cred.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
                    model.linkGoogle(GoogleIdTokenCredential.createFrom(cred.data).idToken)
                } else model.notice = "Google javobi kutilgan turda emas"
            } catch (e: GetCredentialException) {
                model.notice = "Google bilan kirish bekor qilindi yoki sozlanmagan"
            }
        }
    }
}
