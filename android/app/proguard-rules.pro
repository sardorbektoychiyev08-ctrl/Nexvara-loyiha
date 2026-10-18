# No reflection-based app models.

# Credential Manager (Google sign-in) loads the Play Services provider by reflection.
-if class androidx.credentials.CredentialManager
-keep class androidx.credentials.playservices.** { *; }
