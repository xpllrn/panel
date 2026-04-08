package com.cooperative.member.ui.viewmodel;

import androidx.lifecycle.ViewModel;
import com.cooperative.member.data.model.MemberProfile;
import com.cooperative.member.data.repository.MemberRepository;
import com.cooperative.member.util.Resource;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\b\u0007\u0018\u00002\u00020\u0001B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J\u0006\u0010\r\u001a\u00020\u000eR\u001c\u0010\u0005\u001a\u0010\u0012\f\u0012\n\u0012\u0004\u0012\u00020\b\u0018\u00010\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001f\u0010\t\u001a\u0010\u0012\f\u0012\n\u0012\u0004\u0012\u00020\b\u0018\u00010\u00070\n\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\f\u00a8\u0006\u000f"}, d2 = {"Lcom/cooperative/member/ui/viewmodel/ProfileViewModel;", "Landroidx/lifecycle/ViewModel;", "memberRepository", "Lcom/cooperative/member/data/repository/MemberRepository;", "(Lcom/cooperative/member/data/repository/MemberRepository;)V", "_profileState", "Lkotlinx/coroutines/flow/MutableStateFlow;", "Lcom/cooperative/member/util/Resource;", "Lcom/cooperative/member/data/model/MemberProfile;", "profileState", "Lkotlinx/coroutines/flow/StateFlow;", "getProfileState", "()Lkotlinx/coroutines/flow/StateFlow;", "loadProfile", "", "app_debug"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class ProfileViewModel extends androidx.lifecycle.ViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.cooperative.member.data.repository.MemberRepository memberRepository = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.cooperative.member.util.Resource<com.cooperative.member.data.model.MemberProfile>> _profileState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<com.cooperative.member.data.model.MemberProfile>> profileState = null;
    
    @javax.inject.Inject()
    public ProfileViewModel(@org.jetbrains.annotations.NotNull()
    com.cooperative.member.data.repository.MemberRepository memberRepository) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.cooperative.member.util.Resource<com.cooperative.member.data.model.MemberProfile>> getProfileState() {
        return null;
    }
    
    public final void loadProfile() {
    }
}