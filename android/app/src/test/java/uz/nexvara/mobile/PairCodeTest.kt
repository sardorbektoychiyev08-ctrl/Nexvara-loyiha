package uz.nexvara.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class PairCodeTest {
    private val fingerprint = "a".repeat(64)

    @Test fun parsesWindowsPairLink() {
        val code = PairCode.parse("https://192.168.1.10:8765/#p=123456&sid=0123456789abcdef&fp=$fingerprint")
        assertEquals("https://192.168.1.10:8765", code.baseUrl)
        assertEquals("123456", code.code)
        assertEquals(fingerprint, code.fingerprint)
    }

    @Test fun rejectsMissingFingerprint() {
        assertThrows(IllegalArgumentException::class.java) {
            PairCode.parse("https://192.168.1.10:8765/#p=123456&sid=0123456789abcdef")
        }
    }

    @Test fun rejectsHttp() {
        assertThrows(IllegalArgumentException::class.java) {
            PairCode.parse("http://192.168.1.10:8765/#p=123456&sid=0123456789abcdef&fp=$fingerprint")
        }
    }

    @Test fun rejectsTamperedServerIdAndShortFingerprint() {
        assertThrows(IllegalArgumentException::class.java) {
            PairCode.parse("https://192.168.1.10:8765/#p=123456&sid=wrong&fp=$fingerprint")
        }
        assertThrows(IllegalArgumentException::class.java) {
            PairCode.parse("https://192.168.1.10:8765/#p=123456&sid=0123456789abcdef&fp=abcd")
        }
    }

    @Test fun rejectsUnexpectedQueryAndCredentials() {
        assertThrows(IllegalArgumentException::class.java) {
            PairCode.parse("https://192.168.1.10:8765/?x=1#p=123456&sid=0123456789abcdef&fp=$fingerprint")
        }
        assertThrows(IllegalArgumentException::class.java) {
            PairCode.parse("https://user@192.168.1.10:8765/#p=123456&sid=0123456789abcdef&fp=$fingerprint")
        }
    }
}
