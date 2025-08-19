# Note Lifecycle Analysis

Date: 2025-08-19

Scope: End‑to‑end flow for Note items (create, open, edit, auto‑save, rename, move, delete, persist, load, undo/redo) across GUI, model, command, storage, events, and user experience. Includes issues, improvement opportunities, upgrade roadmap, and graded evaluations.

---
## 1. Lifecycle Overview

1. Create → `CreateNoteCommand` adds a `Note` to project tree, emits hierarchical dotted event `note.created` (legacy underscore events removed).
2. Open → Tree double‑click emits event bus UI event `ui.note.open_requested` (Qt signal removed) → `NoteTab` instantiated.
3. Edit Content → User types → local dirty state + 2s debounce auto‑save → `EditNoteCommand` (single mutation path) emits `note.content_changed`.
4. Rename → Either inline tree edit (`RenameItemCommand`) or tab title save button; UI also mutates model directly.
5. Move → Drag/drop in tree triggers `MoveItemCommand` (parent id logic resolved), full tree rebuild.
6. Delete → Context menu triggers `DeleteItemCommand` (not in this file set but implied), tree rebuild; open tabs not guarded.
7. Save Project → `NoteDataManager.save` writes `<id>.md` (content) + `<id>.json` (metadata) during project save.
8. Load Project → `NoteDataManager.load` reconstructs notes from md + json; UI rebuild on `project_loaded`.
9. Undo / Redo → Supported for create & edit (and likely rename/move/delete globally via respective commands). Auto‑save creates many small undo entries.

---
## 2. Detailed Flow & Current Behavior

### 2.1 Creation
Command `CreateNoteCommand`:
- Default name fallback: "New Note" (no collision handling).
- Emits `note.created` only (migration complete; no dual emit).
- Tree refresh still full rebuild (optimization pending).
- Does not auto‑open new note (extra user action needed).

### 2.2 Opening
- Uses event bus UI event `ui.note.open_requested` (Qt signal removed) aligning with event-driven architecture.
- Can still open same note multiple times (de-dup enhancement pending).

### 2.3 Editing Content
- Auto‑save timer (2s) triggers `EditNoteCommand`; UI duplicate mutation removed in migration (single source of truth target—verify remaining UI code for stragglers).
- Emits `note.content_changed` (legacy `note_edited` removed).
- Each auto‑save push still adds full snapshot → undo stack noise & memory overhead (coalescing pending).

### 2.4 Renaming
- Both inline and tab rename flows call `RenameItemCommand` and then locally mutate note name again.
- No uniqueness / validation (duplicate sibling names possible).

### 2.5 Moving
- Drag logic determines new parent id with conditional branching.
- Rebuilds tree wholesale post-move (inefficient).
- Emits generic legacy events; hierarchical dotted form not leveraged.

### 2.6 Deleting
- Potential orphaned open tabs (no warning / closure sync).
- No soft delete or recycle bin.

### 2.7 Persistence (Save / Load)
- Separation of content (.md) and metadata (.json) avoids duplication.
- Metadata timestamps naive (no timezone) and may skew due to double updates.
- Tag list persisted; no UI to edit/filter tags yet.

### 2.8 Undo / Redo
- Works for create & edit but overly granular due to auto‑save frequency; no command coalescing.

### 2.9 Events
- Unified dotted naming (`note.created`, `note.content_changed`, etc.).
- `EventHierarchy` now fully leveraged for notes (generic project events triggered automatically).
- Legacy underscore events and note open Qt signal fully removed.

---
## 3. Key Issues & Risks

| # | Issue | Impact |
|---|-------|--------|
| 1 | (Resolved) Event naming inconsistency | (Addressed in migration) |
| 2 | Duplicate model mutations after commands | Possible divergence when validation is added; timestamp drift |
| 3 | Full tree rebuild on every note change | Performance & UX flicker; scalability concern |
| 4 | Auto‑save creates many undo steps | Poor undo UX, memory overhead |
| 5 | No dirty-close prompt / delete protection | Silent data loss risk |
| 6 | Multiple open tabs for same note allowed | Conflicting edits / last-write-wins ambiguity |
| 7 | Naive timestamps (no tz / double update) | Inconsistent ordering; audit ambiguity |
| 8 | Tags unused in UI | Lost organizational potential |
| 9 | Missing search & filter | Reduced information retrieval efficiency |
| 10 | (Resolved) Legacy events bypass hierarchy | Hierarchy now in effect |
| 11 | No incremental move/update logic | Unnecessary overhead on large projects |
| 12 | No rename validation | Duplicate names reduce clarity |
| 13 | No note diffing (whole content snapshots) | Inefficient memory & potential future sync pain |
| 14 | Missing version history | Hard to recover earlier states beyond coarse undo |
| 15 | Deletion leaves orphan tabs | UI inconsistency, potential exceptions later |

---
## 4. Improvements & Recommendations

### 4.1 Quick Wins (Weeks 1–2)
1. (Done) Event Standardization: Dotted events only; legacy removed.
2. Single Mutation Source: Remove post-command direct `note.update_content` / `update_name` calls in UI; rely on command’s effect and event to refresh.
3. Dirty Close Guard: On tab close or delete → prompt if unsaved (Yes / No / Cancel).
4. Auto‑Save Coalescing: Debounce + if last edit command < N seconds, amend previous command (or maintain content hash to skip no-op saves).
5. Rename Validation: Check sibling set for duplicates; auto-suffix " (2)" pattern.
6. Use timezone-aware UTC timestamps (helper in base Item).

### 4.2 Short Term (Weeks 3–6)
1. Incremental Tree Updates: Insert/move/remove single nodes instead of full rebuild.
2. Tag UI: Simple pill editor + sidebar filter; emit `note.tags_changed` (extend events).
3. Search Index: Lightweight full-text (e.g. Whoosh or rapidfuzz) maintained on content change.
4. Edit Command Coalescing: Group sequential auto-saves into one undo frame (maintain a session window).
5. Unified Event Publisher Utility: `publish_event(enum, payload)` expands hierarchy automatically.

### 4.3 Medium Term (Weeks 6–12)
1. Markdown Preview Split Pane + richer formatting toolbar (headings, lists, code blocks, links, inline math).
2. Version History: Append-only log with snapshot hash + diffs; UI timeline.
3. Cross-Linking: Detect `[[Note:Name]]`, `[[Dataset:ID]]`, `[[Chart:ID]]` tokens → clickable references.
4. Partial Content Diffs: Store diff slices for large notes (foundation for collaboration).

### 4.4 Long Term
1. Real-Time Collaboration (OT/CRDT) with presence indicators.
2. Attachment Embedding (images, equations) managed by asset subsystem.
3. Encryption at rest for note content (optional project setting).
4. Semantic Layer: Summaries, keyword extraction, backlink graph.
5. Plugin Architecture: Register note transformers / renderers.

---
## 5. Proposed Event Mapping (Target State)

| Action | Specific Event | Hierarchy Expansion (auto) |
|--------|----------------|----------------------------|
| Create | `note.created` | `note.created` → `project.item_added` → `project.changed` |
| Rename | `note.renamed` | `note.renamed` → `project.item_renamed` → `project.changed` |
| Delete | `note.deleted` | `note.deleted` → `project.item_removed` → `project.changed` |
| Move | `note.moved` | `note.moved` → `project.item_moved` → `project.changed` |
| Content Edit | `note.content_changed` | `note.content_changed` → `project.changed` |
| Tags Change (new) | `note.tags_changed` | `note.tags_changed` → `project.changed` |

Legacy underscore events: removed (no longer emitted).

---
## 6. Data Model Enhancement Suggestions

| Field | Current | Enhancement |
|-------|---------|-------------|
| `created_at` / `modified_at` | Naive ISO | UTC aware (`datetime.now(tz=UTC)`) |
| `tags` | List, unused | Normalized (case-insensitive set) + indexed |
| `content` | Plain text | Optional markdown + stored hash (SHA-256) |
| (new) `revision_id` | None | Increment each mutation for optimistic concurrency |
| (new) `history` | External (undo only) | Lightweight log entries referencing diff storage |
| (new) `content_hash` | None | Integrity check & fast change detection |

---
## 7. Command Layer Recommendations

1. Introduce a `BaseItemContentCommand` (captures old/new, coalescing policy).  
2. Provide command result object (success, error_code, changed_items) for UI adaptation instead of direct mutation.  
3. Add optional `amend_previous` flag in executor to merge sequential content edits within time window.  
4. Generate standardized events via shared publisher (avoid manual strings).  

---
## 8. GUI / UX Enhancements

| Feature | Value | Notes |
|---------|-------|-------|
| Dirty Indicator in Tree | Quick unsaved visibility | Add a trailing * or italic styling |
| Markdown Preview | Clarity of final output | Re-render on debounce (300ms) |
| Tag Pills + Filter Bar | Organization | Integrate with search index |
| Search Panel | Retrieval speed | Highlight matches; fuzzy ranking |
| Version Timeline | Confidence & recovery | Inline diff viewer |
| Conflict Dialog (multi-tab) | Prevent silent overwrite | Compare hash before save |

---
## 9. Performance Considerations

| Area | Current Cost | Optimization |
|------|--------------|-------------|
| Tree Updates | O(N) rebuild per change | Incremental node ops | 
| Auto-Save | Full text snapshot each time | Coalesce + diff-based storage |
| Search (future) | Linear scan (none) | Maintain incremental index |
| Large Notes | Memory duplication in undo stack | Store diffs / compressed snapshots |

---
## 10. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Event refactor breakage | Dual emit; deprecation warnings; integration tests |
| Undo semantics change | Provide feature flag for coalescing; user setting |
| Incremental tree bugs | Fallback rebuild path behind config until stable |
| Hash-based conflict prompt fatigue | Only prompt when content hashes differ & both modified timestamps advanced |

---
## 11. Grading Summary

| Perspective | Grade | Rationale |
|-------------|-------|-----------|
| Model | B- | Simple and serializable; lacks validation, timezone, versioning, tag usage |
| Command | B | Solid undo/redo & tests; naming + duplication issues |
| GUI | B- | Clean basic editor; limited formatting, no preview/search, redundant mutations |
| User | C+ | Core CRUD only; organizational & retrieval aids missing |

---
## 12. Prioritized Roadmap (High-Level)

| Phase | Goals |
|-------|-------|
| 1 (Weeks 1–2) | Event standardization, duplicate mutation removal, dirty prompt, rename validation, UTC timestamps |
| 2 (Weeks 3–6) | Incremental tree updates, tag UI, search index, command coalescing |
| 3 (Weeks 6–12) | Markdown preview, version history, cross-linking |
| 4 (Long Term) | Collaboration, attachments, encryption, semantic graph, plugin system |

---
## 13. Suggested Initial Task Tickets

1. TASK: Event Normalization & Adapter Layer.  
2. TASK: Remove UI Post-Command Mutations (single source of truth).  
3. TASK: Dirty Close & Delete Protection Dialog.  
4. TASK: Command Coalescing for Auto-Save (EditNote).  
5. TASK: Incremental Tree Update Implementation.  
6. TASK: Tag Pill Editor + Filter Sidebar.  
7. TASK: Basic Full-Text Search (title + content).  
8. TASK: Markdown Preview Pane.  
9. TASK: Note Version History Backend.  
10. TASK: Cross-Link Parsing and Navigation.  

---
## 14. Acceptance Criteria Examples (for Early Tasks)

### Event Normalization (Completed)
- Dotted events (`note.created`, etc.) emitted; legacy underscore events removed.
- Hierarchy expansion verified via `EventHierarchy` mapping.

### Dirty Close Protection
- If note tab has unsaved changes and user closes tab, a modal appears with options: Save / Discard / Cancel.
- Choosing Save runs command & closes tab if success.

### Command Coalescing
- Rapid edits (<5s apart) produce a single undo entry when user presses undo, restoring pre-edit content.

---
## 15. Future Considerations

| Concept | Note |
|---------|------|
| Collaboration | Requires per-range operations (diff granularity) groundwork now |
| Plugins | Define stable `NoteContentChangedEvent` payload schema early |
| Accessibility | Keyboard shortcuts for formatting, ARIA roles for preview |
| Internationalization | Externalize static UI strings in editor widget |

---
## 16. Summary

The Note subsystem is functional with solid command test coverage but limited by inconsistent event naming, redundant state mutations, and lack of organizational and retrieval features. Addressing foundational event and mutation issues unlocks efficient UI scaling; layering search, tags, preview, and version history elevates user experience; longer-term collaboration and semantic features become feasible once diff-friendly structures and clean events exist.

---
## 17. Action Next (Optional Quick Start)

- Start with Event Normalization PR: introduce `events/note_events.py` helper & dual emit.
- Add unit tests for new dotted events + hierarchy mapping.
- Remove duplicate model mutation lines in `note_tab.py` and adjust UI refresh to event subscription.

End of document.
