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
public final class TransactionViewModel_Factory implements Factory<TransactionViewModel> {
  private final Provider<MemberRepository> memberRepositoryProvider;

  public TransactionViewModel_Factory(Provider<MemberRepository> memberRepositoryProvider) {
    this.memberRepositoryProvider = memberRepositoryProvider;
  }

  @Override
  public TransactionViewModel get() {
    return newInstance(memberRepositoryProvider.get());
  }

  public static TransactionViewModel_Factory create(
      Provider<MemberRepository> memberRepositoryProvider) {
    return new TransactionViewModel_Factory(memberRepositoryProvider);
  }

  public static TransactionViewModel newInstance(MemberRepository memberRepository) {
    return new TransactionViewModel(memberRepository);
  }
}
