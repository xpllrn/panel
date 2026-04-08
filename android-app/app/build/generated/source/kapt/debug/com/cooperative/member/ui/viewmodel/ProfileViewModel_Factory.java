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
public final class ProfileViewModel_Factory implements Factory<ProfileViewModel> {
  private final Provider<MemberRepository> memberRepositoryProvider;

  public ProfileViewModel_Factory(Provider<MemberRepository> memberRepositoryProvider) {
    this.memberRepositoryProvider = memberRepositoryProvider;
  }

  @Override
  public ProfileViewModel get() {
    return newInstance(memberRepositoryProvider.get());
  }

  public static ProfileViewModel_Factory create(
      Provider<MemberRepository> memberRepositoryProvider) {
    return new ProfileViewModel_Factory(memberRepositoryProvider);
  }

  public static ProfileViewModel newInstance(MemberRepository memberRepository) {
    return new ProfileViewModel(memberRepository);
  }
}
