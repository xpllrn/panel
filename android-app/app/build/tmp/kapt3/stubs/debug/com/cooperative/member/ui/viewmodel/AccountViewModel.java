package com.cooperative.member.ui.viewmodel;

import androidx.lifecycle.ViewModel;
import com.cooperative.member.data.model.Account;
import com.cooperative.member.data.model.AccountDetail;
import com.cooperative.member.data.repository.MemberRepository;
import com.cooperative.member.util.Resource;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000@\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\b\u0007\u0018\u00002\u00020\u0001B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J\u000e\u0010\u0012\u001a\u00020\u00132\u0006\u0010\u0014\u001a\u00020\u0015J\u0006\u0010\u0016\u001a\u00020\u0013R\u001c\u0010\u0005\u001a\u0010\u0012\f\u0012\n\u0012\u0004\u0012\u00020\b\u0018\u00010\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\"\u0010\t\u001a\u0016\u0012\u0012\u0012\u0010\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u000b0\n\u0018\u00010\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001f\u0010\f\u001a\u0010\u0012\f\u0012\n\u0012\u0004\u0012\u00020\b\u0018\u00010\u00070\r\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000e\u0010\u000fR%\u0010\u0010\u001a\u0016\u0012\u0012\u0012\u0010\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u000b0\n\u0018\u00010\u00070\r\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u000fR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000\u00a8\u0006\u0017"}, d2 = {"Lcom/cooperative/member/ui/viewmodel/AccountViewModel;", "Landroidx/lifecycle/ViewModel;", "memberRepository", "Lcom/cooperative/member/data/repository/MemberRepository;", "(Lcom/cooperative/member/data/repository/MemberRepository;)V", "_accountDetailState", "Lkotlinx/coroutines/flow/MutableStateFlow;", "Lcom/cooperative/member/util/Resource;", "Lcom/cooperative/member/data/model/AccountDetail;", "_accountsState", "", "Lcom/cooperative/member/data/model/Account;", "accountDetailState", "Lkotlinx/coroutines/flow/StateFlow;", "getAccountDetailState", "()Lkotlinx/coroutines/flow/StateFlow;", "accountsState", "getAccountsState", "loadAccountDetail", "", "accountId", "", "loadAccounts", "app_debug"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class AccountViewModel extends androidx.lifecycle.ViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.cooperative.member.data.repository.MemberRepository memberRepository = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Account>>> _accountsState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Account>>> accountsState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.cooperative.member.util.Resource<com.cooperative.member.data.model.AccountDetail>> _accountDetailState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<com.cooperative.member.data.model.AccountDetail>> accountDetailState = null;
    
    @javax.inject.Inject()
    public AccountViewModel(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.repository.MemberRepository memberRepository) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<java.util.List<com.cooperative.member.data.model.Account>>> getAccountsState() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<com.cooperative.member.data.model.AccountDetail>> getAccountDetailState() {
        return null;
    }
    
    public final void loadAccounts() {
    }
    
    public final void loadAccountDetail(int accountId) {
    }
}