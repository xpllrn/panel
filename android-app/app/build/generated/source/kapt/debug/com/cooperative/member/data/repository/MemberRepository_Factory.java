package com.cooperative.member.data.repository;

import com.cooperative.member.data.api.ApiService;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata("javax.inject.Singleton")
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
public final class MemberRepository_Factory implements Factory<MemberRepository> {
  private final Provider<ApiService> apiServiceProvider;

  public MemberRepository_Factory(Provider<ApiService> apiServiceProvider) {
    this.apiServiceProvider = apiServiceProvider;
  }

  @Override
  public MemberRepository get() {
    return newInstance(apiServiceProvider.get());
  }

  public static MemberRepository_Factory create(Provider<ApiService> apiServiceProvider) {
    return new MemberRepository_Factory(apiServiceProvider);
  }

  public static MemberRepository newInstance(ApiService apiService) {
    return new MemberRepository(apiService);
  }
}
