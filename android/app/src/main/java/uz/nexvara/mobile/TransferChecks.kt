package uz.nexvara.mobile

import java.security.MessageDigest

object TransferChecks {
    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    fun matches(bytes: ByteArray, expected: String?): Boolean {
        if (expected == null || !expected.matches(Regex("[0-9a-fA-F]{64}"))) return false
        return MessageDigest.isEqual(
            sha256(bytes).toByteArray(Charsets.US_ASCII),
            expected.lowercase().toByteArray(Charsets.US_ASCII),
        )
    }

    fun resultFileName(path: String): String = path.replace('\\', '/').substringAfterLast('/').ifBlank { "natija" }
}
