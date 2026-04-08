package com.cooperative.member.data.repository;

import com.cooperative.member.data.api.ApiService;
import com.cooperative.member.data.model.*;
import com.cooperative.member.util.Resource;
import javax.inject.Inject;
import javax.inject.Singleton;

@javax.inject.Singleton()
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000V\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0003\b\u0007\u0018\u00002\u00020\u0001B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J\u001c\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u00062\u0006\u0010\b\u001a\u00020\tH\u0086@\u00a2\u0006\u0002\u0010\nJ\u001a\u0010\u000b\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\r0\f0\u0006H\u0086@\u00a2\u0006\u0002\u0010\u000eJ\u0014\u0010\u000f\u001a\b\u0012\u0004\u0012\u00020\u00100\u0006H\u0086@\u00a2\u0006\u0002\u0010\u000eJ\u001c\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\u00120\u00062\u0006\u0010\b\u001a\u00020\tH\u0086@\u00a2\u0006\u0002\u0010\nJ\u001a\u0010\u0013\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u00140\f0\u0006H\u0086@\u00a2\u0006\u0002\u0010\u000eJ\u0014\u0010\u0015\u001a\b\u0012\u0004\u0012\u00020\u00160\u0006H\u0086@\u00a2\u0006\u0002\u0010\u000eJ2\u0010\u0017\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u00180\f0\u00062\n\b\u0002\u0010\u0019\u001a\u0004\u0018\u00010\u001a2\n\b\u0002\u0010\u001b\u001a\u0004\u0018\u00010\tH\u0086@\u00a2\u0006\u0002\u0010\u001cR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000\u00a8\u0006\u001d"}, d2 = {"Lcom/cooperative/member/data/repository/MemberRepository;", "", "apiService", "Lcom/cooperative/member/data/api/ApiService;", "(Lcom/cooperative/member/data/api/ApiService;)V", "getAccountDetail", "Lcom/cooperative/member/util/Resource;", "Lcom/cooperative/member/data/model/AccountDetail;", "id", "", "(ILkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getAccounts", "", "Lcom/cooperative/member/data/model/Account;", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getDashboard", "Lcom/cooperative/member/data/model/DashboardResponse;", "getLoanDetail", "Lcom/cooperative/member/data/model/LoanDetail;", "getLoans", "Lcom/cooperative/member/data/model/Loan;", "getProfile", "Lcom/cooperative/member/data/model/MemberProfile;", "getTransactions", "Lcom/cooperative/member/data/model/Transaction;", "type", "", "accountId", "(Ljava/lang/String;Ljava/lang/Integer;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_debug"})
public final class MemberRepository {
    @org.jetbrains.annotations.NotNull()
    private final com.cooperative.member.data.api.ApiService apiService = null;
    
    @javax.inject.Inject()
    public MemberRepository(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.api.ApiService apiService) {
        super();
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getDashboard(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<com.cooperative.member.data.model.DashboardResponse>> $completion) {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getAccounts(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Account>>> $completion) {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getAccountDetail(int id, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<com.cooperative.member.data.model.AccountDetail>> $completion) {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getLoans(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Loan>>> $completion) {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getLoanDetail(int id, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<com.cooperative.member.data.model.LoanDetail>> $completion) {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getTransactions(@org.jetbrains.annotations.Nullable()
    java.lang.String type, @org.jetbrains.annotations.Nullable()
    java.lang.Integer accountId, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Transaction>>> $completion) {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getProfile(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.cooperative.member.util.Resource<com.cooperative.member.data.model.MemberProfile>> $completion) {
        return null;
    }
}