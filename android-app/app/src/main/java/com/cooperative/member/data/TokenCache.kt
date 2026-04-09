package com.cooperative.member.data

object TokenCache {
    @Volatile
    var accessToken: String? = null
}
