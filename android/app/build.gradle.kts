plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val releaseStore = providers.environmentVariable("NEXVARA_RELEASE_STORE_FILE").orNull
val releaseStorePassword = providers.environmentVariable("NEXVARA_RELEASE_STORE_PASSWORD").orNull
val releaseAlias = providers.environmentVariable("NEXVARA_RELEASE_KEY_ALIAS").orNull
val releaseKeyPassword = providers.environmentVariable("NEXVARA_RELEASE_KEY_PASSWORD").orNull
val releaseInputs = listOf(releaseStore, releaseStorePassword, releaseAlias, releaseKeyPassword)
if (releaseInputs.any { it != null } && releaseInputs.any { it.isNullOrBlank() }) {
    throw GradleException("Release signing uchun 4 ta NEXVARA_RELEASE_* muhit qiymati kerak")
}

android {
    namespace = "uz.nexvara.mobile"
    compileSdk = 36
    defaultConfig {
        applicationId = "uz.nexvara.mobile"
        minSdk = 29
        targetSdk = 36
        versionCode = 10
        versionName = "1.3.0"
    }
    signingConfigs {
        if (releaseStore != null) create("nexvaraRelease") {
            storeFile = file(releaseStore)
            storePassword = releaseStorePassword
            keyAlias = releaseAlias
            keyPassword = releaseKeyPassword
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            signingConfig = signingConfigs.findByName("nexvaraRelease")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.09.00"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.3")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("androidx.biometric:biometric:1.1.0")  // app lock
    implementation("androidx.work:work-runtime-ktx:2.10.1")  // "task finished" while the app is closed
    implementation("com.google.android.gms:play-services-mlkit-document-scanner:16.0.0")  // paper â†’ PDF
    // Google sign-in on the phone (Credential Manager); the PC verifies the ID token.
    implementation("androidx.credentials:credentials:1.5.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.5.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.1.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")  // real org.json for JVM unit tests
}
