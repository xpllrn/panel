package com.cooperative.member.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cooperative.member.ui.viewmodel.LoginState
import com.cooperative.member.ui.viewmodel.LoginViewModel

@Composable
fun LoginScreen(vm: LoginViewModel) {
    val state by vm.state.collectAsState()
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var otp by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    val focusManager = LocalFocusManager.current
    val otpState = state as? LoginState.OtpRequired
    val isCredLoading = state is LoginState.LoadingCredentials
    val isOtpLoading = state is LoginState.VerifyingOtp

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Brand logo
        Surface(
            modifier = Modifier.size(80.dp),
            shape = CircleShape,
            color = MaterialTheme.colorScheme.primary
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    "P",
                    style = MaterialTheme.typography.headlineLarge.copy(
                        fontWeight = FontWeight.Black,
                        fontSize = 32.sp
                    ),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            }
        }

        Spacer(Modifier.height(24.dp))

        Text(
            if (otpState == null) "Welcome back" else "Enter OTP",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onBackground
        )

        Text(
            if (otpState == null) "Sign in to your Panels account" else "Enter the 6-digit code sent to your email",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp)
        )

        Spacer(Modifier.height(22.dp))

        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 1.dp
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                // Error banner
                AnimatedVisibility(
                    visible = state is LoginState.Error,
                    enter = fadeIn(),
                    exit = fadeOut()
                ) {
                    val msg = (state as? LoginState.Error)?.message ?: ""
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 16.dp),
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.errorContainer
                    ) {
                        Text(
                            msg,
                            modifier = Modifier.padding(14.dp),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }

                if (otpState == null) {
                    OutlinedTextField(
                        value = username,
                        onValueChange = { username = it; vm.clearError() },
                        label = { Text("Username") },
                        singleLine = true,
                        enabled = !isCredLoading,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        colors = fieldColors(),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                        keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) })
                    )

                    Spacer(Modifier.height(14.dp))

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it; vm.clearError() },
                        label = { Text("Password") },
                        singleLine = true,
                        enabled = !isCredLoading,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        colors = fieldColors(),
                        visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { showPassword = !showPassword }) {
                                Icon(
                                    if (showPassword) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                    contentDescription = "Toggle password"
                                )
                            }
                        },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = {
                            focusManager.clearFocus()
                            vm.login(username, password)
                        })
                    )
                } else {
                    OtpCodeField(
                        value = otp,
                        enabled = !isOtpLoading,
                        onValueChange = {
                            otp = it
                            vm.clearError()
                        },
                        onDone = {
                            focusManager.clearFocus()
                            vm.verifyOtp(otp)
                        }
                    )
                    Spacer(Modifier.height(10.dp))
                    val mins = otpState.secondsLeft / 60
                    val secs = otpState.secondsLeft % 60
                    Text(
                        text = String.format("OTP expires in %02d:%02d", mins, secs),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(6.dp))
                    TextButton(onClick = { vm.resendOtp() }, enabled = otpState.secondsLeft <= 0 && !isOtpLoading) {
                        Text("Resend OTP")
                    }
                    TextButton(
                        onClick = {
                            otp = ""
                            vm.backToCredentials()
                        },
                        enabled = !isOtpLoading
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("Use different account")
                    }
                }

                Spacer(Modifier.height(20.dp))

                // Sign in button
                Button(
                    onClick = {
                        focusManager.clearFocus()
                        if (otpState == null) vm.login(username, password) else vm.verifyOtp(otp)
                    },
                    enabled = !isCredLoading && !isOtpLoading,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    if (isCredLoading || isOtpLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            if (otpState == null) "Send OTP" else "Verify OTP",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = MaterialTheme.colorScheme.primary,
    unfocusedBorderColor = MaterialTheme.colorScheme.outline,
    focusedLabelColor = MaterialTheme.colorScheme.primary,
    cursorColor = MaterialTheme.colorScheme.primary
)

@Composable
private fun OtpCodeField(
    value: String,
    enabled: Boolean,
    onValueChange: (String) -> Unit,
    onDone: () -> Unit
) {
    val focusRequester = remember { FocusRequester() }
    BasicTextField(
        value = value,
        onValueChange = { input ->
            onValueChange(input.filter { it.isDigit() }.take(6))
        },
        enabled = enabled,
        singleLine = true,
        textStyle = TextStyle(color = Color.Transparent),
        cursorBrush = SolidColor(Color.Transparent),
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.NumberPassword,
            imeAction = ImeAction.Done
        ),
        keyboardActions = KeyboardActions(onDone = { onDone() }),
        modifier = Modifier
            .fillMaxWidth()
            .focusRequester(focusRequester)
            .clickable(enabled = enabled) { focusRequester.requestFocus() },
        decorationBox = {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                repeat(6) { index ->
                    val digit = value.getOrNull(index)?.toString() ?: ""
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(56.dp)
                            .border(
                                width = 1.dp,
                                color = if (index == value.length && value.length < 6) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.outline
                                },
                                shape = RoundedCornerShape(12.dp)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = digit,
                            style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.onBackground,
                            textAlign = TextAlign.Center
                        )
                    }
                }
            }
        }
    )

    LaunchedEffect(enabled) {
        if (enabled) {
            focusRequester.requestFocus()
        }
    }
}
