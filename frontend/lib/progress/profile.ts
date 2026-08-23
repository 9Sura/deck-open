// A tiny local identity (plan 08 §5, sub-plan §8) — just a name + avatar emoji
// to greet the user and to seed the guest→account migration story. No auth, no
// network. Kept as *data* now even though Phase 1 surfaces no edit UI (that
// slides to Phase 2 with the dashboard); migration needs something to carry.

const PROFILE_KEY = "deck-profile";

export interface Profile {
  displayName: string;
  avatarEmoji: string;
  createdTs: number;
}

export function defaultProfile(): Profile {
  return { displayName: "Guest", avatarEmoji: "📝", createdTs: Date.now() };
}

/** Read the stored profile, or null if none / storage is blocked. */
export function readProfile(): Profile | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Profile>;
    if (typeof parsed.displayName !== "string") return null;
    return {
      displayName: parsed.displayName,
      avatarEmoji:
        typeof parsed.avatarEmoji === "string" ? parsed.avatarEmoji : "📝",
      createdTs: typeof parsed.createdTs === "number" ? parsed.createdTs : Date.now(),
    };
  } catch {
    return null; // private mode / corrupt JSON — treat as no profile
  }
}

/** Persist the profile; a no-op if storage is unavailable (private mode). */
export function writeProfile(p: Profile): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(p));
  } catch {
    /* storage blocked — the profile just won't persist this session */
  }
}
