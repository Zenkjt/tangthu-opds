package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestWriteCatalogBranchShardsAndPages(t *testing.T) {
	out := t.TempDir()
	files := make([]FileEntry, 0, 1003)
	files = append(files, FileEntry{ID: "folder-A", ParentID: "root-A", Name: "Subfolder", IsFolder: true})
	for i := 0; i < 1001; i++ {
		files = append(files, FileEntry{ID: fmtID(i), ParentID: "root-A", Name: "Book", MIME: "application/epub+zip"})
	}
	files = append(files, FileEntry{ID: "nested-book", ParentID: "folder-A", Name: "Nested.epub"})
	branch := Branch{Config: BranchConfig{ID: "shelf-A", DisplayName: "Shelf A", RootFolderID: "root-A"}, DriveFolderName: "Drive A", Files: files}

	if err := writeCatalogBranchShards(out, branch); err != nil {
		t.Fatal(err)
	}
	rootPath := filepath.Join(out, "catalog", "shelf-A", "root.json")
	data, err := os.ReadFile(rootPath)
	if err != nil {
		t.Fatal(err)
	}
	var root struct {
		BranchID    string             `json:"branch_id"`
		RootShards  []string           `json:"root_shards"`
		Directories []catalogDirectory `json:"directories"`
	}
	if err := json.Unmarshal(data, &root); err != nil {
		t.Fatal(err)
	}
	if root.BranchID != "shelf-A" {
		t.Fatalf("branch id = %q", root.BranchID)
	}
	if len(root.RootShards) != 2 {
		t.Fatalf("expected 2 root pages, got %d", len(root.RootShards))
	}
	if len(root.Directories) != 1 || len(root.Directories[0].Shards) != 1 {
		t.Fatalf("unexpected directory index: %#v", root.Directories)
	}

	nestedPath := filepath.Join(out, filepath.FromSlash(root.Directories[0].Shards[0]))
	nestedData, err := os.ReadFile(nestedPath)
	if err != nil {
		t.Fatal(err)
	}
	var nested struct {
		FolderID string        `json:"folder_id"`
		Items    []catalogFile `json:"items"`
	}
	if err := json.Unmarshal(nestedData, &nested); err != nil {
		t.Fatal(err)
	}
	if nested.FolderID != "folder-A" || len(nested.Items) != 1 || nested.Items[0].ID != "nested-book" {
		t.Fatalf("unexpected nested shard: %#v", nested)
	}
}

func TestMergeCatalogShardsPreservesOtherBranches(t *testing.T) {
	out := t.TempDir()
	first := Branch{Config: BranchConfig{ID: "A", DisplayName: "A", RootFolderID: "root-A"}, Files: []FileEntry{{ID: "a1", ParentID: "root-A", Name: "A.epub"}}}
	second := Branch{Config: BranchConfig{ID: "B", DisplayName: "B", RootFolderID: "root-B"}, Files: []FileEntry{{ID: "b1", ParentID: "root-B", Name: "B.epub"}}}
	if err := writeCatalogShards(out, []Branch{first, second}); err != nil {
		t.Fatal(err)
	}
	if err := writeCatalogManifest(out, []Branch{first, second}); err != nil {
		t.Fatal(err)
	}

	updated := Branch{Config: BranchConfig{ID: "A", DisplayName: "A renamed", RootFolderID: "root-A"}, Files: []FileEntry{{ID: "a2", ParentID: "root-A", Name: "New.epub"}}}
	if err := mergeCatalogShards(out, []Branch{updated}); err != nil {
		t.Fatal(err)
	}
	manifest, err := readCatalogManifest(filepath.Join(out, "catalog.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(manifest.Branches) != 2 {
		t.Fatalf("expected 2 branches, got %d", len(manifest.Branches))
	}
	if manifest.Branches[0].Name != "A renamed" || manifest.Branches[1].ID != "B" {
		t.Fatalf("unexpected merged manifest: %#v", manifest.Branches)
	}
}

func fmtID(i int) string { return fmt.Sprintf("book-%04d", i) }

func TestEmptyDirectoryShardListIsEmptyArray(t *testing.T) {
	out := t.TempDir()
	branch := Branch{
		Config: BranchConfig{ID: "shelf-empty", DisplayName: "Shelf", RootFolderID: "root"},
		Files:  []FileEntry{{ID: "empty-folder", ParentID: "root", Name: "Empty", IsFolder: true}},
	}
	if err := writeCatalogBranchShards(out, branch); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(out, "catalog", "shelf-empty", "root.json"))
	if err != nil {
		t.Fatal(err)
	}
	var root struct {
		Directories []struct {
			ID     string   `json:"id"`
			Shards []string `json:"shards"`
		} `json:"directories"`
	}
	if err := json.Unmarshal(data, &root); err != nil {
		t.Fatal(err)
	}
	if len(root.Directories) != 1 || root.Directories[0].ID != "empty-folder" {
		t.Fatalf("unexpected directory metadata: %#v", root.Directories)
	}
	if root.Directories[0].Shards == nil || len(root.Directories[0].Shards) != 0 {
		t.Fatalf("empty directory shards must be [], got %#v", root.Directories[0].Shards)
	}
}

func TestBranchLessPrioritizesVNThenAlphabetical(t *testing.T) {
	got := []string{"Sách Yến", "VN02", "ABC", "VN01"}
	for i := 0; i < len(got); i++ {
		for j := i + 1; j < len(got); j++ {
			if branchLess(got[j], got[i]) {
				got[i], got[j] = got[j], got[i]
			}
		}
	}
	want := []string{"VN01", "VN02", "ABC", "Sách Yến"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("sorted branches = %#v, want %#v", got, want)
		}
	}
}
