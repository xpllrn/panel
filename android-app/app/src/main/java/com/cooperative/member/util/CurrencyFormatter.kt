package com.cooperative.member.util

import java.math.BigDecimal
import java.math.RoundingMode

object Fmt {

    fun rupee(value: String): String {
        val bd = try {
            BigDecimal(value.replace(",", "")).setScale(0, RoundingMode.HALF_UP)
        } catch (_: NumberFormatException) {
            return "\u20B90"
        }
        val negative = bd.signum() < 0
        val abs = bd.abs().toPlainString()
        val formatted = indianGroup(abs)
        return if (negative) "-\u20B9$formatted" else "\u20B9$formatted"
    }

    fun withSign(value: String, isCredit: Boolean): String {
        val r = rupee(value)
        return if (isCredit) "+$r" else "-$r"
    }

    private fun indianGroup(s: String): String {
        if (s.length <= 3) return s
        val last3 = s.takeLast(3)
        val rest = s.dropLast(3)
        val groups = mutableListOf(last3)
        var remaining = rest
        while (remaining.isNotEmpty()) {
            groups.add(0, remaining.takeLast(2))
            remaining = if (remaining.length > 2) remaining.dropLast(2) else ""
        }
        return groups.joinToString(",")
    }
}
