"use client";

import type { PushConfig } from "@/lib/api/types";
import { getPushSubscription, hasServerKey, NoServiceWorkerError, sha256Hex, subscribeBrowser } from "@/lib/push";
import { parentApi, type PushSubscriptionInput } from "./api";

export type PushEnableResult = "enabled" | "denied" | "dismissed" | "no-worker";

/** Per-device convenience flag: which parent turned push on in this browser. Not a credential. */
export const PUSH_DEVICE_KEY = "ud_push_parent";
const LOGOUT_TIMEOUT_MS = 3000;

function rememberDevice(parentUserId: string) {
  try {
    window.localStorage.setItem(PUSH_DEVICE_KEY, parentUserId);
  } catch {
    // Storage unavailable: push still works, only the automatic re-sync after a key rotation is lost.
  }
}

function forgetDevice() {
  try {
    window.localStorage.removeItem(PUSH_DEVICE_KEY);
  } catch {
    // Nothing to forget.
  }
}

export function isDeviceOf(parentUserId: string): boolean {
  try {
    return window.localStorage.getItem(PUSH_DEVICE_KEY) === parentUserId;
  } catch {
    return false;
  }
}

function toInput(subscription: PushSubscription): PushSubscriptionInput {
  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    throw new Error("Push subscription is missing its keys");
  }
  return { endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } };
}

export interface PushState {
  config: PushConfig;
  subscription: PushSubscription | null;
}

/** What the browser and the server know about push on this device. The endpoint itself never leaves the page. */
export async function readPushState(): Promise<PushState> {
  const subscription = await getPushSubscription();
  const config = await parentApi.pushConfig(subscription ? await sha256Hex(subscription.endpoint) : undefined);
  return { config, subscription };
}

/**
 * The push service replaced the subscription (`pushsubscriptionchange` in the worker): the browser holds a
 * subscription for our server key that the backend does not know. Re-register it, but only for the parent
 * who enabled push on this device — someone else's leftover subscription stays off until they toggle it.
 */
export async function resyncPush(state: PushState, parentUserId: string): Promise<boolean> {
  const { config, subscription } = state;
  if (!subscription || config.subscribed || !config.enabled || !config.public_key) return false;
  if (!isDeviceOf(parentUserId) || !hasServerKey(subscription, config.public_key)) return false;
  await parentApi.savePushSubscription(toInput(subscription));
  return true;
}

/** Ask for permission, subscribe the browser and register this device with the backend. */
export async function enablePush(publicKey: string, parentUserId: string): Promise<PushEnableResult> {
  const permission = await Notification.requestPermission();
  if (permission === "denied") return "denied";
  if (permission !== "granted") return "dismissed";
  let subscription: PushSubscription;
  try {
    subscription = await subscribeBrowser(publicKey);
  } catch (error) {
    if (error instanceof NoServiceWorkerError) return "no-worker";
    throw error;
  }
  await parentApi.savePushSubscription(toInput(subscription));
  rememberDevice(parentUserId);
  return "enabled";
}

/**
 * Forget this device on the server first (that needs the session), then locally — but only when the server
 * confirms the subscription was ours: on a shared phone another parent's subscription survives our toggle.
 */
export async function disablePush(): Promise<void> {
  forgetDevice();
  const subscription = await getPushSubscription();
  if (!subscription) return;
  const { deleted } = await parentApi.deletePushSubscription(subscription.endpoint);
  if (deleted > 0) await subscription.unsubscribe();
}

/**
 * A parent logs out: this device must stop receiving their notifications. Never throws and never holds the
 * logout for long. When the server cannot be asked (offline, session already gone) the browser subscription
 * is dropped anyway; the backend prunes the dead endpoint on its next push.
 */
export async function forgetPushOnLogout(): Promise<void> {
  const timeout = new Promise<void>((resolve) => setTimeout(resolve, LOGOUT_TIMEOUT_MS));
  const work = disablePush()
    .catch(async () => {
      const subscription = await getPushSubscription();
      await subscription?.unsubscribe();
    })
    .catch(() => undefined);
  await Promise.race([work, timeout]);
}
