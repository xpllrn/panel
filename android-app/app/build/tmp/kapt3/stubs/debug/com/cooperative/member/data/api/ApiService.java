package com.cooperative.member.data.api;

import com.cooperative.member.data.model.*;
import retrofit2.Response;
import retrofit2.http.*;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000f\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\bf\u0018\u00002\u00020\u0001J\u001e\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u00032\b\b\u0001\u0010\u0005\u001a\u00020\u0006H\u00a7@\u00a2\u0006\u0002\u0010\u0007J,\u0010\b\u001a\b\u0012\u0004\u0012\u00020\t0\u00032\n\b\u0003\u0010\n\u001a\u0004\u0018\u00010\u00062\n\b\u0003\u0010\u000b\u001a\u0004\u0018\u00010\u0006H\u00a7@\u00a2\u0006\u0002\u0010\fJ\u0014\u0010\r\u001a\b\u0012\u0004\u0012\u00020\u000e0\u0003H\u00a7@\u00a2\u0006\u0002\u0010\u000fJ\u001e\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00110\u00032\b\b\u0001\u0010\u0005\u001a\u00020\u0006H\u00a7@\u00a2\u0006\u0002\u0010\u0007J,\u0010\u0012\u001a\b\u0012\u0004\u0012\u00020\u00130\u00032\n\b\u0003\u0010\n\u001a\u0004\u0018\u00010\u00062\n\b\u0003\u0010\u000b\u001a\u0004\u0018\u00010\u0006H\u00a7@\u00a2\u0006\u0002\u0010\fJ\u0014\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\u00150\u0003H\u00a7@\u00a2\u0006\u0002\u0010\u000fJD\u0010\u0016\u001a\b\u0012\u0004\u0012\u00020\u00170\u00032\n\b\u0003\u0010\u0018\u001a\u0004\u0018\u00010\u00192\n\b\u0003\u0010\u001a\u001a\u0004\u0018\u00010\u00062\n\b\u0003\u0010\n\u001a\u0004\u0018\u00010\u00062\n\b\u0003\u0010\u000b\u001a\u0004\u0018\u00010\u0006H\u00a7@\u00a2\u0006\u0002\u0010\u001bJ\u001e\u0010\u001c\u001a\b\u0012\u0004\u0012\u00020\u001d0\u00032\b\b\u0001\u0010\u001e\u001a\u00020\u001fH\u00a7@\u00a2\u0006\u0002\u0010 J\u001e\u0010!\u001a\b\u0012\u0004\u0012\u00020\"0\u00032\b\b\u0001\u0010\u001e\u001a\u00020#H\u00a7@\u00a2\u0006\u0002\u0010$\u00a8\u0006%"}, d2 = {"Lcom/cooperative/member/data/api/ApiService;", "", "getAccountDetail", "Lretrofit2/Response;", "Lcom/cooperative/member/data/model/AccountDetail;", "id", "", "(ILkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getAccounts", "Lcom/cooperative/member/data/model/AccountsListResponse;", "page", "pageSize", "(Ljava/lang/Integer;Ljava/lang/Integer;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getDashboard", "Lcom/cooperative/member/data/model/DashboardResponse;", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getLoanDetail", "Lcom/cooperative/member/data/model/LoanDetail;", "getLoans", "Lcom/cooperative/member/data/model/LoansListResponse;", "getProfile", "Lcom/cooperative/member/data/model/MemberProfile;", "getTransactions", "Lcom/cooperative/member/data/api/TransactionsListResponse;", "type", "", "accountId", "(Ljava/lang/String;Ljava/lang/Integer;Ljava/lang/Integer;Ljava/lang/Integer;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "login", "Lcom/cooperative/member/data/model/LoginResponse;", "request", "Lcom/cooperative/member/data/model/LoginRequest;", "(Lcom/cooperative/member/data/model/LoginRequest;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "refreshToken", "Lcom/cooperative/member/data/model/RefreshResponse;", "Lcom/cooperative/member/data/model/RefreshRequest;", "(Lcom/cooperative/member/data/model/RefreshRequest;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_debug"})
public abstract interface ApiService {
    
    @retrofit2.http.POST(value = "auth/login/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object login(@retrofit2.http.Body()
    @org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.model.LoginRequest request, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.LoginResponse>> $completion);
    
    @retrofit2.http.POST(value = "auth/refresh/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object refreshToken(@retrofit2.http.Body()
    @org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.model.RefreshRequest request, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.RefreshResponse>> $completion);
    
    @retrofit2.http.GET(value = "auth/profile/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getProfile(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.MemberProfile>> $completion);
    
    @retrofit2.http.GET(value = "member/dashboard/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getDashboard(@org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.DashboardResponse>> $completion);
    
    @retrofit2.http.GET(value = "member/accounts/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getAccounts(@retrofit2.http.Query(value = "page")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer page, @retrofit2.http.Query(value = "page_size")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer pageSize, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.AccountsListResponse>> $completion);
    
    @retrofit2.http.GET(value = "member/accounts/{id}/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getAccountDetail(@retrofit2.http.Path(value = "id")
    int id, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.AccountDetail>> $completion);
    
    @retrofit2.http.GET(value = "member/loans/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getLoans(@retrofit2.http.Query(value = "page")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer page, @retrofit2.http.Query(value = "page_size")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer pageSize, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.LoansListResponse>> $completion);
    
    @retrofit2.http.GET(value = "member/loans/{id}/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getLoanDetail(@retrofit2.http.Path(value = "id")
    int id, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.model.LoanDetail>> $completion);
    
    @retrofit2.http.GET(value = "member/transactions/")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getTransactions(@retrofit2.http.Query(value = "type")
    @org.jetbrains.annotations.Nullable()
    java.lang.String type, @retrofit2.http.Query(value = "account")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer accountId, @retrofit2.http.Query(value = "page")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer page, @retrofit2.http.Query(value = "page_size")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer pageSize, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super retrofit2.Response<com.cooperative.member.data.api.TransactionsListResponse>> $completion);
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 3, xi = 48)
    public static final class DefaultImpls {
    }
}