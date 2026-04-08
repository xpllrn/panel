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
public final class DashboardViewModel_Factory implements Factory<DashboardViewModel> {
  private final Provider<MemberRepository> memberRepositoryProvider;

  public DashboardViewModel_Factory(Provider<MemberRepository> memberRepositoryProvider) {
    this.memberRepositoryProvider = memberRepositoryProvider;
  }

  @Override
  public DashboardViewModel get() {
    return newInstance(memberRepositoryProvider.get());
  }

  public static DashboardViewModel_Factory create(
      Provider<MemberRepository> memberRepositoryProvider) {
    return new DashboardViewModel_Factory(memberRepositoryProvider);
  }

  public static DashboardViewModel newInstance(MemberRepository memberRepository) {
    return new DashboardViewModel(memberRepository);
  }
}
