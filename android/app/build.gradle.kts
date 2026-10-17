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
        versionCode = 1
        versionName = "0.1.0"
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
    buildFeatures { compose = true }
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
    testImplementation("junit:junit:4.13.2")
}
