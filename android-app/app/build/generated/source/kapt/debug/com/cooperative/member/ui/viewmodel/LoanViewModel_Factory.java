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
public final class LoanViewModel_Factory implements Factory<LoanViewModel> {
  private final Provider<MemberRepository> memberRepositoryProvider;

  public LoanViewModel_Factory(Provider<MemberRepository> memberRepositoryProvider) {
    this.memberRepositoryProvider = memberRepositoryProvider;
  }

  @Override
  public LoanViewModel get() {
    return newInstance(memberRepositoryProvider.get());
  }

  public static LoanViewModel_Factory create(Provider<MemberRepository> memberRepositoryProvider) {
    return new LoanViewModel_Factory(memberRepositoryProvider);
  }

  public static LoanViewModel newInstance(MemberRepository memberRepository) {
    return new LoanViewModel(memberRepository);
  }
}
