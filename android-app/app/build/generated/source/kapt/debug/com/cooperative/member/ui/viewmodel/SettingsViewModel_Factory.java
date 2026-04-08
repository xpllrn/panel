package com.cooperative.member.ui.viewmodel;

import com.cooperative.member.data.preferences.ThemeManager;
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
public final class SettingsViewModel_Factory implements Factory<SettingsViewModel> {
  private final Provider<ThemeManager> themeManagerProvider;

  public SettingsViewModel_Factory(Provider<ThemeManager> themeManagerProvider) {
    this.themeManagerProvider = themeManagerProvider;
  }

  @Override
  public SettingsViewModel get() {
    return newInstance(themeManagerProvider.get());
  }

  public static SettingsViewModel_Factory create(Provider<ThemeManager> themeManagerProvider) {
    return new SettingsViewModel_Factory(themeManagerProvider);
  }

  public static SettingsViewModel newInstance(ThemeManager themeManager) {
    return new SettingsViewModel(themeManager);
  }
}
