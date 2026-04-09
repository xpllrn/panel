package com.cooperative.member

import android.app.Application
import com.cooperative.member.data.ApiClient
import com.cooperative.member.data.MemberRepository
import com.cooperative.member.data.SessionManager

class CooperativeApp : Application() {

    lateinit var session: SessionManager
        private set

    lateinit var repository: MemberRepository
        private set

    override fun onCreate() {
        super.onCreate()
        session = SessionManager(this)
        val api = ApiClient.create(session)
        repository = MemberRepository(api, session)
    }
}
