package com.cooperative.member.data.preferences;

import android.content.Context;
import dagger.internal.DaggerGenerated;
import dagger.internal.Factory;
import dagger.internal.QualifierMetadata;
import dagger.internal.ScopeMetadata;
import javax.annotation.processing.Generated;
import javax.inject.Provider;

@ScopeMetadata("javax.inject.Singleton")
@QualifierMetadata("dagger.hilt.android.qualifiers.ApplicationContext")
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
public final class ThemeManager_Factory implements Factory<ThemeManager> {
  private final Provider<Context> contextProvider;

  public ThemeManager_Factory(Provider<Context> contextProvider) {
    this.contextProvider = contextProvider;
  }

  @Override
  public ThemeManager get() {
    return newInstance(contextProvider.get());
  }

  public static ThemeManager_Factory create(Provider<Context> contextProvider) {
    return new ThemeManager_Factory(contextProvider);
  }

  public static ThemeManager newInstance(Context context) {
    return new ThemeManager(context);
  }
}
