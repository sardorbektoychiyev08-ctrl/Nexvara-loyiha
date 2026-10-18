package uz.nexvara.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TransferChecksTest {
    private val bytes = "NEXVARA".toByteArray()

    @Test fun acceptsMatchingResultDigest() {
        assertTrue(TransferChecks.matches(bytes, TransferChecks.sha256(bytes).uppercase()))
    }

    @Test fun rejectsChangedResultAndMissingDigest() {
        val digest = TransferChecks.sha256(bytes)
        assertFalse(TransferChecks.matches("NEXVARB".toByteArray(), digest))
        assertFalse(TransferChecks.matches(bytes, null))
        assertFalse(TransferChecks.matches(bytes, "bad"))
    }

    @Test fun namesWindowsAndUnixResults() {
        assertEquals("hisobot.xlsx", TransferChecks.resultFileName("D:\\NEXVARA\\hisobot.xlsx"))
        assertEquals("natija.pdf", TransferChecks.resultFileName("/tmp/natija.pdf"))
    }
}
