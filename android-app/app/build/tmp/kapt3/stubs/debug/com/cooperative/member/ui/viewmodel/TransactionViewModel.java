package com.cooperative.member.ui.viewmodel;

import androidx.lifecycle.ViewModel;
import com.cooperative.member.data.model.Transaction;
import com.cooperative.member.data.repository.MemberRepository;
import com.cooperative.member.util.Resource;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000@\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\b\u0007\u0018\u00002\u00020\u0001B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J#\u0010\u000e\u001a\u00020\u000f2\n\b\u0002\u0010\u0010\u001a\u0004\u0018\u00010\u00112\n\b\u0002\u0010\u0012\u001a\u0004\u0018\u00010\u0013\u00a2\u0006\u0002\u0010\u0014R\"\u0010\u0005\u001a\u0016\u0012\u0012\u0012\u0010\u0012\n\u0012\b\u0012\u0004\u0012\u00020\t0\b\u0018\u00010\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R%\u0010\n\u001a\u0016\u0012\u0012\u0012\u0010\u0012\n\u0012\b\u0012\u0004\u0012\u00020\t0\b\u0018\u00010\u00070\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b\f\u0010\r\u00a8\u0006\u0015"}, d2 = {"Lcom/cooperative/member/ui/viewmodel/TransactionViewModel;", "Landroidx/lifecycle/ViewModel;", "memberRepository", "Lcom/cooperative/member/data/repository/MemberRepository;", "(Lcom/cooperative/member/data/repository/MemberRepository;)V", "_transactionsState", "Lkotlinx/coroutines/flow/MutableStateFlow;", "Lcom/cooperative/member/util/Resource;", "", "Lcom/cooperative/member/data/model/Transaction;", "transactionsState", "Lkotlinx/coroutines/flow/StateFlow;", "getTransactionsState", "()Lkotlinx/coroutines/flow/StateFlow;", "loadTransactions", "", "type", "", "accountId", "", "(Ljava/lang/String;Ljava/lang/Integer;)V", "app_debug"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class TransactionViewModel extends androidx.lifecycle.ViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.cooperative.member.data.repository.MemberRepository memberRepository = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Transaction>>> _transactionsState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Transaction>>> transactionsState = null;
    
    @javax.inject.Inject()
    public TransactionViewModel(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.repository.MemberRepository memberRepository) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Transaction>>> getTransactionsState() {
        return null;
    }
    
    public final void loadTransactions(@org.jetbrains.annotations.Nullable()
    java.lang.String type, @org.jetbrains.annotations.Nullable()
    java.lang.Integer accountId) {
    }
}