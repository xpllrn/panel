package com.cooperative.member.ui.viewmodel;

import com.cooperative.member.data.repository.MemberRepository;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata
@QualifierMetadata
@DaggerGenerated
@Generated(
    value = "dagger.internal.codegen.ComponentProcessor",
    comments = "https://dagger.dev"
)
@SuppressWarnings({
    "unchecked",
    "rawtypes",
    "KotlinInternal",
    "KotlinInternalInJava",
    "cast"
})
public final class AccountViewModel_Factory implements Factory<AccountViewModel> {
  private final Provider<MemberRepository> memberRepositoryProvider;

  public AccountViewModel_Factory(Provider<MemberRepository> memberRepositoryProvider) {
    this.memberRepositoryProvider = memberRepositoryProvider;
  }

  @Override
  public AccountViewModel get() {
    return newInstance(memberRepositoryProvider.get());
  }

  public static AccountViewModel_Factory create(
      Provider<MemberRepository> memberRepositoryProvider) {
    return new AccountViewModel_Factory(memberRepositoryProvider);
  }

  public static AccountViewModel newInstance(MemberRepository memberRepository) {
    return new AccountViewModel(memberRepository);
  }
}
