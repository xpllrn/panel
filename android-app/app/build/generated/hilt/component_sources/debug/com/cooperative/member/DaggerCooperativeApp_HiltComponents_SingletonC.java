package com.cooperative.member;

import android.app.Activity;
import android.app.Service;
import android.view.View;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.SavedStateHandle;
import androidx.lifecycle.ViewModel;
import com.cooperative.member.data.api.ApiService;
import com.cooperative.member.data.api.AuthInterceptor;
import com.cooperative.member.data.preferences.ThemeManager;
import com.cooperative.member.data.repository.AuthRepository;
import com.cooperative.member.data.repository.MemberRepository;
import com.cooperative.member.data.repository.TokenManager;
import com.cooperative.member.di.NetworkModule_ProvideApiServiceFactory;
import com.cooperative.member.di.NetworkModule_ProvideOkHttpClientFactory;
import com.cooperative.member.di.NetworkModule_ProvideRetrofitFactory;
import com.cooperative.member.ui.viewmodel.AccountViewModel;
import com.cooperative.member.ui.viewmodel.AccountViewModel_HiltModules;
import com.cooperative.member.ui.viewmodel.DashboardViewModel;
import com.cooperative.member.ui.viewmodel.DashboardViewModel_HiltModules;
import com.cooperative.member.ui.viewmodel.LoanViewModel;
import com.cooperative.member.ui.viewmodel.LoanViewModel_HiltModules;
import com.cooperative.member.ui.viewmodel.LoginViewModel;
import com.cooperative.member.ui.viewmodel.LoginViewModel_HiltModules;
import com.cooperative.member.ui.viewmodel.ProfileViewModel;
import com.cooperative.member.ui.viewmodel.ProfileViewModel_HiltModules;
import com.cooperative.member.ui.viewmodel.SettingsViewModel;
import com.cooperative.member.ui.viewmodel.SettingsViewModel_HiltModules;
import com.cooperative.member.ui.viewmodel.TransactionViewModel;
import com.cooperative.member.ui.viewmodel.TransactionViewModel_HiltModules;
import dagger.hilt.android.ActivityRetainedLifecycle;
import dagger.hilt.android.ViewModelLifecycle;
import dagger.hilt.android.internal.builders.ActivityComponentBuilder;
import dagger.hilt.android.internal.builders.ActivityRetainedComponentBuilder;
import dagger.hilt.android.internal.builders.FragmentComponentBuilder;
import dagger.hilt.android.internal.builders.ServiceComponentBuilder;
import dagger.hilt.android.internal.builders.ViewComponentBuilder;
import dagger.hilt.android.internal.builders.ViewModelComponentBuilder;
import dagger.hilt.android.internal.builders.ViewWithFragmentComponentBuilder;
import dagger.hilt.android.internal.lifecycle.DefaultViewModelFactories;
import dagger.hilt.android.internal.lifecycle.DefaultViewModelFactories_InternalFactoryFactory_Factory;
import dagger.hilt.android.internal.managers.ActivityRetainedComponentManager_LifecycleModule_ProvideActivityRetainedLifecycleFactory;
import dagger.hilt.android.internal.managers.SavedStateHandleHolder;
import dagger.hilt.android.internal.modules.ApplicationContextModule;
import dagger.hilt.android.internal.modules.ApplicationContextModule_ProvideContextFactory;
import dagger.internal.DaggerGenerated;
import dagger.internal.DoubleCheck;
import dagger.internal.IdentifierNameString;
import dagger.internal.KeepFieldType;
import dagger.internal.LazyClassKeyMap;
import dagger.internal.MapBuilder;
import dagger.internal.Preconditions;
import dagger.internal.Provider;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import javax.annotation.processing.Generated;
import okhttp3.OkHttpClient;
import retrofit2.Retrofit;

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
public final class DaggerCooperativeApp_HiltComponents_SingletonC {
  private DaggerCooperativeApp_HiltComponents_SingletonC() {
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private ApplicationContextModule applicationContextModule;

    private Builder() {
    }

    public Builder applicationContextModule(ApplicationContextModule applicationContextModule) {
      this.applicationContextModule = Preconditions.checkNotNull(applicationContextModule);
      return this;
    }

    public CooperativeApp_HiltComponents.SingletonC build() {
      Preconditions.checkBuilderRequirement(applicationContextModule, ApplicationContextModule.class);
      return new SingletonCImpl(applicationContextModule);
    }
  }

  private static final class ActivityRetainedCBuilder implements CooperativeApp_HiltComponents.ActivityRetainedC.Builder {
    private final SingletonCImpl singletonCImpl;

    private SavedStateHandleHolder savedStateHandleHolder;

    private ActivityRetainedCBuilder(SingletonCImpl singletonCImpl) {
      this.singletonCImpl = singletonCImpl;
    }

    @Override
    public ActivityRetainedCBuilder savedStateHandleHolder(
        SavedStateHandleHolder savedStateHandleHolder) {
      this.savedStateHandleHolder = Preconditions.checkNotNull(savedStateHandleHolder);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.ActivityRetainedC build() {
      Preconditions.checkBuilderRequirement(savedStateHandleHolder, SavedStateHandleHolder.class);
      return new ActivityRetainedCImpl(singletonCImpl, savedStateHandleHolder);
    }
  }

  private static final class ActivityCBuilder implements CooperativeApp_HiltComponents.ActivityC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private Activity activity;

    private ActivityCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
    }

    @Override
    public ActivityCBuilder activity(Activity activity) {
      this.activity = Preconditions.checkNotNull(activity);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.ActivityC build() {
      Preconditions.checkBuilderRequirement(activity, Activity.class);
      return new ActivityCImpl(singletonCImpl, activityRetainedCImpl, activity);
    }
  }

  private static final class FragmentCBuilder implements CooperativeApp_HiltComponents.FragmentC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private Fragment fragment;

    private FragmentCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
    }

    @Override
    public FragmentCBuilder fragment(Fragment fragment) {
      this.fragment = Preconditions.checkNotNull(fragment);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.FragmentC build() {
      Preconditions.checkBuilderRequirement(fragment, Fragment.class);
      return new FragmentCImpl(singletonCImpl, activityRetainedCImpl, activityCImpl, fragment);
    }
  }

  private static final class ViewWithFragmentCBuilder implements CooperativeApp_HiltComponents.ViewWithFragmentC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final FragmentCImpl fragmentCImpl;

    private View view;

    private ViewWithFragmentCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl,
        FragmentCImpl fragmentCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
      this.fragmentCImpl = fragmentCImpl;
    }

    @Override
    public ViewWithFragmentCBuilder view(View view) {
      this.view = Preconditions.checkNotNull(view);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.ViewWithFragmentC build() {
      Preconditions.checkBuilderRequirement(view, View.class);
      return new ViewWithFragmentCImpl(singletonCImpl, activityRetainedCImpl, activityCImpl, fragmentCImpl, view);
    }
  }

  private static final class ViewCBuilder implements CooperativeApp_HiltComponents.ViewC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private View view;

    private ViewCBuilder(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        ActivityCImpl activityCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
    }

    @Override
    public ViewCBuilder view(View view) {
      this.view = Preconditions.checkNotNull(view);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.ViewC build() {
      Preconditions.checkBuilderRequirement(view, View.class);
      return new ViewCImpl(singletonCImpl, activityRetainedCImpl, activityCImpl, view);
    }
  }

  private static final class ViewModelCBuilder implements CooperativeApp_HiltComponents.ViewModelC.Builder {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private SavedStateHandle savedStateHandle;

    private ViewModelLifecycle viewModelLifecycle;

    private ViewModelCBuilder(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
    }

    @Override
    public ViewModelCBuilder savedStateHandle(SavedStateHandle handle) {
      this.savedStateHandle = Preconditions.checkNotNull(handle);
      return this;
    }

    @Override
    public ViewModelCBuilder viewModelLifecycle(ViewModelLifecycle viewModelLifecycle) {
      this.viewModelLifecycle = Preconditions.checkNotNull(viewModelLifecycle);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.ViewModelC build() {
      Preconditions.checkBuilderRequirement(savedStateHandle, SavedStateHandle.class);
      Preconditions.checkBuilderRequirement(viewModelLifecycle, ViewModelLifecycle.class);
      return new ViewModelCImpl(singletonCImpl, activityRetainedCImpl, savedStateHandle, viewModelLifecycle);
    }
  }

  private static final class ServiceCBuilder implements CooperativeApp_HiltComponents.ServiceC.Builder {
    private final SingletonCImpl singletonCImpl;

    private Service service;

    private ServiceCBuilder(SingletonCImpl singletonCImpl) {
      this.singletonCImpl = singletonCImpl;
    }

    @Override
    public ServiceCBuilder service(Service service) {
      this.service = Preconditions.checkNotNull(service);
      return this;
    }

    @Override
    public CooperativeApp_HiltComponents.ServiceC build() {
      Preconditions.checkBuilderRequirement(service, Service.class);
      return new ServiceCImpl(singletonCImpl, service);
    }
  }

  private static final class ViewWithFragmentCImpl extends CooperativeApp_HiltComponents.ViewWithFragmentC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final FragmentCImpl fragmentCImpl;

    private final ViewWithFragmentCImpl viewWithFragmentCImpl = this;

    private ViewWithFragmentCImpl(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl,
        FragmentCImpl fragmentCImpl, View viewParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;
      this.fragmentCImpl = fragmentCImpl;


    }
  }

  private static final class FragmentCImpl extends CooperativeApp_HiltComponents.FragmentC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final FragmentCImpl fragmentCImpl = this;

    private FragmentCImpl(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, ActivityCImpl activityCImpl,
        Fragment fragmentParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;


    }

    @Override
    public DefaultViewModelFactories.InternalFactoryFactory getHiltInternalFactoryFactory() {
      return activityCImpl.getHiltInternalFactoryFactory();
    }

    @Override
    public ViewWithFragmentComponentBuilder viewWithFragmentComponentBuilder() {
      return new ViewWithFragmentCBuilder(singletonCImpl, activityRetainedCImpl, activityCImpl, fragmentCImpl);
    }
  }

  private static final class ViewCImpl extends CooperativeApp_HiltComponents.ViewC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl;

    private final ViewCImpl viewCImpl = this;

    private ViewCImpl(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
        ActivityCImpl activityCImpl, View viewParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;
      this.activityCImpl = activityCImpl;


    }
  }

  private static final class ActivityCImpl extends CooperativeApp_HiltComponents.ActivityC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ActivityCImpl activityCImpl = this;

    private ActivityCImpl(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, Activity activityParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;


    }

    @Override
    public void injectMainActivity(MainActivity arg0) {
      injectMainActivity2(arg0);
    }

    @Override
    public DefaultViewModelFactories.InternalFactoryFactory getHiltInternalFactoryFactory() {
      return DefaultViewModelFactories_InternalFactoryFactory_Factory.newInstance(getViewModelKeys(), new ViewModelCBuilder(singletonCImpl, activityRetainedCImpl));
    }

    @Override
    public Map<Class<?>, Boolean> getViewModelKeys() {
      return LazyClassKeyMap.<Boolean>of(MapBuilder.<String, Boolean>newMapBuilder(7).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_AccountViewModel, AccountViewModel_HiltModules.KeyModule.provide()).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_DashboardViewModel, DashboardViewModel_HiltModules.KeyModule.provide()).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_LoanViewModel, LoanViewModel_HiltModules.KeyModule.provide()).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_LoginViewModel, LoginViewModel_HiltModules.KeyModule.provide()).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_ProfileViewModel, ProfileViewModel_HiltModules.KeyModule.provide()).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_SettingsViewModel, SettingsViewModel_HiltModules.KeyModule.provide()).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_TransactionViewModel, TransactionViewModel_HiltModules.KeyModule.provide()).build());
    }

    @Override
    public ViewModelComponentBuilder getViewModelComponentBuilder() {
      return new ViewModelCBuilder(singletonCImpl, activityRetainedCImpl);
    }

    @Override
    public FragmentComponentBuilder fragmentComponentBuilder() {
      return new FragmentCBuilder(singletonCImpl, activityRetainedCImpl, activityCImpl);
    }

    @Override
    public ViewComponentBuilder viewComponentBuilder() {
      return new ViewCBuilder(singletonCImpl, activityRetainedCImpl, activityCImpl);
    }

    private MainActivity injectMainActivity2(MainActivity instance) {
      MainActivity_MembersInjector.injectThemeManager(instance, singletonCImpl.themeManagerProvider.get());
      return instance;
    }

    @IdentifierNameString
    private static final class LazyClassKeyProvider {
      static String com_cooperative_member_ui_viewmodel_AccountViewModel = "com.cooperative.member.ui.viewmodel.AccountViewModel";

      static String com_cooperative_member_ui_viewmodel_ProfileViewModel = "com.cooperative.member.ui.viewmodel.ProfileViewModel";

      static String com_cooperative_member_ui_viewmodel_LoanViewModel = "com.cooperative.member.ui.viewmodel.LoanViewModel";

      static String com_cooperative_member_ui_viewmodel_LoginViewModel = "com.cooperative.member.ui.viewmodel.LoginViewModel";

      static String com_cooperative_member_ui_viewmodel_TransactionViewModel = "com.cooperative.member.ui.viewmodel.TransactionViewModel";

      static String com_cooperative_member_ui_viewmodel_SettingsViewModel = "com.cooperative.member.ui.viewmodel.SettingsViewModel";

      static String com_cooperative_member_ui_viewmodel_DashboardViewModel = "com.cooperative.member.ui.viewmodel.DashboardViewModel";

      @KeepFieldType
      AccountViewModel com_cooperative_member_ui_viewmodel_AccountViewModel2;

      @KeepFieldType
      ProfileViewModel com_cooperative_member_ui_viewmodel_ProfileViewModel2;

      @KeepFieldType
      LoanViewModel com_cooperative_member_ui_viewmodel_LoanViewModel2;

      @KeepFieldType
      LoginViewModel com_cooperative_member_ui_viewmodel_LoginViewModel2;

      @KeepFieldType
      TransactionViewModel com_cooperative_member_ui_viewmodel_TransactionViewModel2;

      @KeepFieldType
      SettingsViewModel com_cooperative_member_ui_viewmodel_SettingsViewModel2;

      @KeepFieldType
      DashboardViewModel com_cooperative_member_ui_viewmodel_DashboardViewModel2;
    }
  }

  private static final class ViewModelCImpl extends CooperativeApp_HiltComponents.ViewModelC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl;

    private final ViewModelCImpl viewModelCImpl = this;

    private Provider<AccountViewModel> accountViewModelProvider;

    private Provider<DashboardViewModel> dashboardViewModelProvider;

    private Provider<LoanViewModel> loanViewModelProvider;

    private Provider<LoginViewModel> loginViewModelProvider;

    private Provider<ProfileViewModel> profileViewModelProvider;

    private Provider<SettingsViewModel> settingsViewModelProvider;

    private Provider<TransactionViewModel> transactionViewModelProvider;

    private ViewModelCImpl(SingletonCImpl singletonCImpl,
        ActivityRetainedCImpl activityRetainedCImpl, SavedStateHandle savedStateHandleParam,
        ViewModelLifecycle viewModelLifecycleParam) {
      this.singletonCImpl = singletonCImpl;
      this.activityRetainedCImpl = activityRetainedCImpl;

      initialize(savedStateHandleParam, viewModelLifecycleParam);

    }

    @SuppressWarnings("unchecked")
    private void initialize(final SavedStateHandle savedStateHandleParam,
        final ViewModelLifecycle viewModelLifecycleParam) {
      this.accountViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 0);
      this.dashboardViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 1);
      this.loanViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 2);
      this.loginViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 3);
      this.profileViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 4);
      this.settingsViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 5);
      this.transactionViewModelProvider = new SwitchingProvider<>(singletonCImpl, activityRetainedCImpl, viewModelCImpl, 6);
    }

    @Override
    public Map<Class<?>, javax.inject.Provider<ViewModel>> getHiltViewModelMap() {
      return LazyClassKeyMap.<javax.inject.Provider<ViewModel>>of(MapBuilder.<String, javax.inject.Provider<ViewModel>>newMapBuilder(7).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_AccountViewModel, ((Provider) accountViewModelProvider)).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_DashboardViewModel, ((Provider) dashboardViewModelProvider)).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_LoanViewModel, ((Provider) loanViewModelProvider)).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_LoginViewModel, ((Provider) loginViewModelProvider)).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_ProfileViewModel, ((Provider) profileViewModelProvider)).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_SettingsViewModel, ((Provider) settingsViewModelProvider)).put(LazyClassKeyProvider.com_cooperative_member_ui_viewmodel_TransactionViewModel, ((Provider) transactionViewModelProvider)).build());
    }

    @Override
    public Map<Class<?>, Object> getHiltViewModelAssistedMap() {
      return Collections.<Class<?>, Object>emptyMap();
    }

    @IdentifierNameString
    private static final class LazyClassKeyProvider {
      static String com_cooperative_member_ui_viewmodel_TransactionViewModel = "com.cooperative.member.ui.viewmodel.TransactionViewModel";

      static String com_cooperative_member_ui_viewmodel_ProfileViewModel = "com.cooperative.member.ui.viewmodel.ProfileViewModel";

      static String com_cooperative_member_ui_viewmodel_SettingsViewModel = "com.cooperative.member.ui.viewmodel.SettingsViewModel";

      static String com_cooperative_member_ui_viewmodel_AccountViewModel = "com.cooperative.member.ui.viewmodel.AccountViewModel";

      static String com_cooperative_member_ui_viewmodel_LoginViewModel = "com.cooperative.member.ui.viewmodel.LoginViewModel";

      static String com_cooperative_member_ui_viewmodel_DashboardViewModel = "com.cooperative.member.ui.viewmodel.DashboardViewModel";

      static String com_cooperative_member_ui_viewmodel_LoanViewModel = "com.cooperative.member.ui.viewmodel.LoanViewModel";

      @KeepFieldType
      TransactionViewModel com_cooperative_member_ui_viewmodel_TransactionViewModel2;

      @KeepFieldType
      ProfileViewModel com_cooperative_member_ui_viewmodel_ProfileViewModel2;

      @KeepFieldType
      SettingsViewModel com_cooperative_member_ui_viewmodel_SettingsViewModel2;

      @KeepFieldType
      AccountViewModel com_cooperative_member_ui_viewmodel_AccountViewModel2;

      @KeepFieldType
      LoginViewModel com_cooperative_member_ui_viewmodel_LoginViewModel2;

      @KeepFieldType
      DashboardViewModel com_cooperative_member_ui_viewmodel_DashboardViewModel2;

      @KeepFieldType
      LoanViewModel com_cooperative_member_ui_viewmodel_LoanViewModel2;
    }

    private static final class SwitchingProvider<T> implements Provider<T> {
      private final SingletonCImpl singletonCImpl;

      private final ActivityRetainedCImpl activityRetainedCImpl;

      private final ViewModelCImpl viewModelCImpl;

      private final int id;

      SwitchingProvider(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
          ViewModelCImpl viewModelCImpl, int id) {
        this.singletonCImpl = singletonCImpl;
        this.activityRetainedCImpl = activityRetainedCImpl;
        this.viewModelCImpl = viewModelCImpl;
        this.id = id;
      }

      @SuppressWarnings("unchecked")
      @Override
      public T get() {
        switch (id) {
          case 0: // com.cooperative.member.ui.viewmodel.AccountViewModel 
          return (T) new AccountViewModel(singletonCImpl.memberRepositoryProvider.get());

          case 1: // com.cooperative.member.ui.viewmodel.DashboardViewModel 
          return (T) new DashboardViewModel(singletonCImpl.memberRepositoryProvider.get());

          case 2: // com.cooperative.member.ui.viewmodel.LoanViewModel 
          return (T) new LoanViewModel(singletonCImpl.memberRepositoryProvider.get());

          case 3: // com.cooperative.member.ui.viewmodel.LoginViewModel 
          return (T) new LoginViewModel(singletonCImpl.authRepositoryProvider.get());

          case 4: // com.cooperative.member.ui.viewmodel.ProfileViewModel 
          return (T) new ProfileViewModel(singletonCImpl.memberRepositoryProvider.get());

          case 5: // com.cooperative.member.ui.viewmodel.SettingsViewModel 
          return (T) new SettingsViewModel(singletonCImpl.themeManagerProvider.get());

          case 6: // com.cooperative.member.ui.viewmodel.TransactionViewModel 
          return (T) new TransactionViewModel(singletonCImpl.memberRepositoryProvider.get());

          default: throw new AssertionError(id);
        }
      }
    }
  }

  private static final class ActivityRetainedCImpl extends CooperativeApp_HiltComponents.ActivityRetainedC {
    private final SingletonCImpl singletonCImpl;

    private final ActivityRetainedCImpl activityRetainedCImpl = this;

    private Provider<ActivityRetainedLifecycle> provideActivityRetainedLifecycleProvider;

    private ActivityRetainedCImpl(SingletonCImpl singletonCImpl,
        SavedStateHandleHolder savedStateHandleHolderParam) {
      this.singletonCImpl = singletonCImpl;

      initialize(savedStateHandleHolderParam);

    }

    @SuppressWarnings("unchecked")
    private void initialize(final SavedStateHandleHolder savedStateHandleHolderParam) {
      this.provideActivityRetainedLifecycleProvider = DoubleCheck.provider(new SwitchingProvider<ActivityRetainedLifecycle>(singletonCImpl, activityRetainedCImpl, 0));
    }

    @Override
    public ActivityComponentBuilder activityComponentBuilder() {
      return new ActivityCBuilder(singletonCImpl, activityRetainedCImpl);
    }

    @Override
    public ActivityRetainedLifecycle getActivityRetainedLifecycle() {
      return provideActivityRetainedLifecycleProvider.get();
    }

    private static final class SwitchingProvider<T> implements Provider<T> {
      private final SingletonCImpl singletonCImpl;

      private final ActivityRetainedCImpl activityRetainedCImpl;

      private final int id;

      SwitchingProvider(SingletonCImpl singletonCImpl, ActivityRetainedCImpl activityRetainedCImpl,
          int id) {
        this.singletonCImpl = singletonCImpl;
        this.activityRetainedCImpl = activityRetainedCImpl;
        this.id = id;
      }

      @SuppressWarnings("unchecked")
      @Override
      public T get() {
        switch (id) {
          case 0: // dagger.hilt.android.ActivityRetainedLifecycle 
          return (T) ActivityRetainedComponentManager_LifecycleModule_ProvideActivityRetainedLifecycleFactory.provideActivityRetainedLifecycle();

          default: throw new AssertionError(id);
        }
      }
    }
  }

  private static final class ServiceCImpl extends CooperativeApp_HiltComponents.ServiceC {
    private final SingletonCImpl singletonCImpl;

    private final ServiceCImpl serviceCImpl = this;

    private ServiceCImpl(SingletonCImpl singletonCImpl, Service serviceParam) {
      this.singletonCImpl = singletonCImpl;


    }
  }

  private static final class SingletonCImpl extends CooperativeApp_HiltComponents.SingletonC {
    private final ApplicationContextModule applicationContextModule;

    private final SingletonCImpl singletonCImpl = this;

    private Provider<ThemeManager> themeManagerProvider;

    private Provider<TokenManager> tokenManagerProvider;

    private Provider<OkHttpClient> provideOkHttpClientProvider;

    private Provider<Retrofit> provideRetrofitProvider;

    private Provider<ApiService> provideApiServiceProvider;

    private Provider<MemberRepository> memberRepositoryProvider;

    private Provider<AuthRepository> authRepositoryProvider;

    private SingletonCImpl(ApplicationContextModule applicationContextModuleParam) {
      this.applicationContextModule = applicationContextModuleParam;
      initialize(applicationContextModuleParam);

    }

    private AuthInterceptor authInterceptor() {
      return new AuthInterceptor(tokenManagerProvider.get());
    }

    @SuppressWarnings("unchecked")
    private void initialize(final ApplicationContextModule applicationContextModuleParam) {
      this.themeManagerProvider = DoubleCheck.provider(new SwitchingProvider<ThemeManager>(singletonCImpl, 0));
      this.tokenManagerProvider = DoubleCheck.provider(new SwitchingProvider<TokenManager>(singletonCImpl, 5));
      this.provideOkHttpClientProvider = DoubleCheck.provider(new SwitchingProvider<OkHttpClient>(singletonCImpl, 4));
      this.provideRetrofitProvider = DoubleCheck.provider(new SwitchingProvider<Retrofit>(singletonCImpl, 3));
      this.provideApiServiceProvider = DoubleCheck.provider(new SwitchingProvider<ApiService>(singletonCImpl, 2));
      this.memberRepositoryProvider = DoubleCheck.provider(new SwitchingProvider<MemberRepository>(singletonCImpl, 1));
      this.authRepositoryProvider = DoubleCheck.provider(new SwitchingProvider<AuthRepository>(singletonCImpl, 6));
    }

    @Override
    public void injectCooperativeApp(CooperativeApp cooperativeApp) {
    }

    @Override
    public Set<Boolean> getDisableFragmentGetContextFix() {
      return Collections.<Boolean>emptySet();
    }

    @Override
    public ActivityRetainedComponentBuilder retainedComponentBuilder() {
      return new ActivityRetainedCBuilder(singletonCImpl);
    }

    @Override
    public ServiceComponentBuilder serviceComponentBuilder() {
      return new ServiceCBuilder(singletonCImpl);
    }

    private static final class SwitchingProvider<T> implements Provider<T> {
      private final SingletonCImpl singletonCImpl;

      private final int id;

      SwitchingProvider(SingletonCImpl singletonCImpl, int id) {
        this.singletonCImpl = singletonCImpl;
        this.id = id;
      }

      @SuppressWarnings("unchecked")
      @Override
      public T get() {
        switch (id) {
          case 0: // com.cooperative.member.data.preferences.ThemeManager 
          return (T) new ThemeManager(ApplicationContextModule_ProvideContextFactory.provideContext(singletonCImpl.applicationContextModule));

          case 1: // com.cooperative.member.data.repository.MemberRepository 
          return (T) new MemberRepository(singletonCImpl.provideApiServiceProvider.get());

          case 2: // com.cooperative.member.data.api.ApiService 
          return (T) NetworkModule_ProvideApiServiceFactory.provideApiService(singletonCImpl.provideRetrofitProvider.get());

          case 3: // retrofit2.Retrofit 
          return (T) NetworkModule_ProvideRetrofitFactory.provideRetrofit(singletonCImpl.provideOkHttpClientProvider.get());

          case 4: // okhttp3.OkHttpClient 
          return (T) NetworkModule_ProvideOkHttpClientFactory.provideOkHttpClient(singletonCImpl.authInterceptor());

          case 5: // com.cooperative.member.data.repository.TokenManager 
          return (T) new TokenManager(ApplicationContextModule_ProvideContextFactory.provideContext(singletonCImpl.applicationContextModule));

          case 6: // com.cooperative.member.data.repository.AuthRepository 
          return (T) new AuthRepository(singletonCImpl.provideApiServiceProvider.get(), singletonCImpl.tokenManagerProvider.get());

          default: throw new AssertionError(id);
        }
      }
    }
  }
}
