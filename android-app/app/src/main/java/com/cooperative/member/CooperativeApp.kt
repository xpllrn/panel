package com.panels.danc

import android.app.Application
import com.panels.danc.data.ApiClient
import com.panels.danc.data.MemberRepository
import com.panels.danc.data.SessionManager
import kotlinx.coroutines.runBlocking

class CooperativeApp : Application() {

    lateinit var session: SessionManager
        private set

    lateinit var repository: MemberRepository
        private set

    override fun onCreate() {
        super.onCreate()
        session = SessionManager(this)
        runBlocking {
            session.syncCacheFromStorage()
        }
        val api = ApiClient.create(session)
        repository = MemberRepository(api, session)
    }
}
