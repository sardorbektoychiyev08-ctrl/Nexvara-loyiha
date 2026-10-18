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
        handleOpen(intent)
        Reminders.schedule(this)
        NexvaraWidget.refresh(this)
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
            val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
                if (granted) startDictation() else model.notice = "Mikrofon ruxsati berilmadi"
            }
            val scanLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { r ->
                if (r.resultCode == RESULT_OK) {
                    com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult.fromActivityResultIntent(r.data)
                        ?.pdf?.uri?.let { model.upload(it) }
                }
            }
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
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE, model.voiceLang)
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
                confirm = ::confirmWithLock,
                reschedule = { Reminders.schedule(this) },
                startDictation = {
                    if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) startDictation()
                    else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                },
                stopDictation = ::stopDictation,
                copyText = { text ->
                    getSystemService(android.content.ClipboardManager::class.java)
                        ?.setPrimaryClip(android.content.ClipData.newPlainText("NEXVARA", text))
                    model.notice = "Nusxa olindi"
                },
                scanDocument = {
                    val options = com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions.Builder()
                        .setGalleryImportAllowed(true).setPageLimit(30)
                        .setResultFormats(com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions.RESULT_FORMAT_PDF)
                        .setScannerMode(com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions.SCANNER_MODE_FULL).build()
                    com.google.mlkit.vision.documentscanner.GmsDocumentScanning.getClient(options).getStartScanIntent(this)
                        .addOnSuccessListener { scanLauncher.launch(androidx.activity.result.IntentSenderRequest.Builder(it).build()) }
                        .addOnFailureListener { model.notice = "Skaner ochilmadi (Google Play xizmatlari kerak)" }
                },
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
        handleOpen(intent)
    }

    /** Widget buttons and lesson reminders open a screen directly. */
    private fun handleOpen(intent: Intent?) {
        val name = intent?.getStringExtra("open") ?: return
        intent.removeExtra("open")
        runCatching { Screen.valueOf(name) }.getOrNull()?.let { if (model.profile != null || it == Screen.Schedule) model.open(it) }
    }

    /** Fingerprint / PIN before something sensitive (controlling the PC). */
    private fun confirmWithLock(reason: String, ok: () -> Unit) {
        val km = getSystemService(android.app.KeyguardManager::class.java)
        if (km?.isDeviceSecure != true) { ok(); return }
        val strong = BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        val info = BiometricPrompt.PromptInfo.Builder().setTitle(reason).setSubtitle("Tasdiqlang")
        if (Build.VERSION.SDK_INT >= 30) info.setAllowedAuthenticators(strong)
        else @Suppress("DEPRECATION") info.setDeviceCredentialAllowed(true)
        BiometricPrompt(this, ContextCompat.getMainExecutor(this), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) { ok() }
        }).authenticate(info.build())
    }

    // ---------------- meeting notes: continuous speech recognition ----------------
    private var recognizer: android.speech.SpeechRecognizer? = null

    private fun startDictation() {
        if (!android.speech.SpeechRecognizer.isRecognitionAvailable(this)) { model.notice = "Telefonda ovozni tanish xizmati yo‘q"; return }
        model.tools.dictating = true
        val r = recognizer ?: android.speech.SpeechRecognizer.createSpeechRecognizer(this).also { recognizer = it }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, model.voiceLang)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            // A speaker pauses to think: do not end the piece on a short silence.
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000)
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 3000)
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 15000)
            .apply {
                if (Build.VERSION.SDK_INT >= 33) {  // punctuation and capitals by the phone's recognizer
                    putExtra(RecognizerIntent.EXTRA_ENABLE_FORMATTING, RecognizerIntent.FORMATTING_OPTIMIZE_QUALITY)
                }
            }
        r.setRecognitionListener(object : android.speech.RecognitionListener {
            override fun onResults(results: Bundle?) {
                results?.getStringArrayList(android.speech.SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let {
                    model.tools.dictation = (model.tools.dictation + " " + sentence(it)).trim()
                }
                model.tools.partial = ""
                if (model.tools.dictating) r.startListening(intent)  // keep listening until "To‘xtatish"
            }
            override fun onPartialResults(partial: Bundle?) {
                model.tools.partial = partial?.getStringArrayList(android.speech.SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
            }
            override fun onError(error: Int) {
                if (model.tools.dictating && error != android.speech.SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                    window.decorView.postDelayed({ if (model.tools.dictating) r.startListening(intent) }, 400)
                } else stopDictation()
            }
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        r.startListening(intent)
    }

    private fun stopDictation() {
        model.tools.dictating = false
        model.tools.partial = ""
        recognizer?.stopListening()
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

    override fun onDestroy() { tts?.shutdown(); tts = null; recognizer?.destroy(); recognizer = null; super.onDestroy() }

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
