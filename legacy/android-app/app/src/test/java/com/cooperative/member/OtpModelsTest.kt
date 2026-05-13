package com.panels.danc

import com.panels.danc.data.LoginStartResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class OtpModelsTest {

    @Test
    fun loginStartResponse_defaultsAreSafe() {
        val response = LoginStartResponse()
        assertFalse(response.success)
        assertEquals("", response.challenge_token)
        assertEquals(0, response.expires_in_seconds)
    }
}
