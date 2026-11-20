package drive

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	apiBase           = "https://www.googleapis.com/drive/v3"
	folderMIME        = "application/vnd.google-apps.folder"
	maxAPIRetries     = 3
	apiRetryBaseDelay = 2 * time.Second
)

type File struct {
	ID             string `json:"id"`
	ParentID       string `json:"-"`
	Name           string `json:"name"`
	MIMEType       string `json:"mimeType"`
	Size           int64  `json:"size,string"`
	ModifiedTime   string `json:"modifiedTime"`
	MD5Checksum    string `json:"md5Checksum"`
	WebContentLink string `json:"webContentLink"`
}

type Client struct {
	apiKey string
	http   *http.Client
}

type listResponse struct {
	NextPageToken string `json:"nextPageToken"`
	Files         []File `json:"files"`
}

func NewClient(apiKey string) (*Client, error) {
	if strings.TrimSpace(apiKey) == "" {
		return nil, errors.New("Google Drive API key is not configured")
	}
	return &Client{apiKey: strings.TrimSpace(apiKey), http: http.DefaultClient}, nil
}

// get retries transient Google Drive API failures. This protects large catalog
// scans from short-lived 429/5xx failures without changing the scan architecture.
func (c *Client) get(ctx context.Context, endpoint string, params url.Values, dst any) error {
	params.Set("key", c.apiKey)
	u := apiBase + endpoint + "?" + params.Encode()

	var lastErr error
	for attempt := 0; attempt <= maxAPIRetries; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
		if err != nil {
			return err
		}
		req.Header.Set("Accept", "application/json")

		resp, err := c.http.Do(req)
		if err != nil {
			if !isRetryableNetworkError(err) || attempt == maxAPIRetries {
				return err
			}
			lastErr = err
			if err := waitForRetry(ctx, attempt, 0); err != nil {
				return err
			}
			continue
		}

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			if len(body) == 0 {
				return errors.New("Google Drive API returned an empty response")
			}
			if err := json.Unmarshal(body, dst); err != nil {
				if attempt == maxAPIRetries {
					return err
				}
				lastErr = err
				if err := waitForRetry(ctx, attempt, 0); err != nil {
					return err
				}
				continue
			}
			return nil
		}

		lastErr = fmt.Errorf(
			"Google Drive API returned %s: %s",
			resp.Status,
			strings.TrimSpace(string(body)),
		)
		if !isRetryableStatus(resp.StatusCode) || attempt == maxAPIRetries {
			return lastErr
		}

		if err := waitForRetry(ctx, attempt, retryAfter(resp.Header)); err != nil {
			return err
		}
	}

	return lastErr
}

func isRetryableStatus(status int) bool {
	switch status {
	case http.StatusTooManyRequests,
		http.StatusInternalServerError,
		http.StatusBadGateway,
		http.StatusServiceUnavailable,
		http.StatusGatewayTimeout:
		return true
	default:
		return false
	}
}

func isRetryableNetworkError(err error) bool {
	if err == nil {
		return false
	}
	return true
}

func retryAfter(header http.Header) time.Duration {
	value := strings.TrimSpace(header.Get("Retry-After"))
	if value == "" {
		return 0
	}

	seconds, err := strconv.Atoi(value)
	if err == nil && seconds >= 0 {
		return time.Duration(seconds) * time.Second
	}

	if when, err := http.ParseTime(value); err == nil {
		if delay := time.Until(when); delay > 0 {
			return delay
		}
	}
	return 0
}

func waitForRetry(ctx context.Context, attempt int, serverDelay time.Duration) error {
	delay := serverDelay
	if delay <= 0 {
		delay = apiRetryBaseDelay * time.Duration(1<<attempt)
	}

	timer := time.NewTimer(delay)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func (c *Client) GetFolder(ctx context.Context, id string) (File, error) {
	var f File
	err := c.get(ctx, "/files/"+url.PathEscape(id), url.Values{"fields": {"id,name,mimeType"}, "supportsAllDrives": {"true"}}, &f)
	if err != nil {
		return File{}, err
	}
	if f.MIMEType != folderMIME {
		return File{}, fmt.Errorf("Google Drive item %q is not a folder", id)
	}
	return f, nil
}

func (c *Client) ListChildren(ctx context.Context, parentID string) ([]File, error) {
	var all []File
	var token string
	for {
		q := fmt.Sprintf("'%s' in parents and trashed = false", escapeQuery(parentID))
		params := url.Values{
			"q": {q}, "pageSize": {"1000"}, "orderBy": {"folder,name"},
			"fields":            {"nextPageToken,files(id,name,mimeType,size,modifiedTime,md5Checksum,webContentLink)"},
			"supportsAllDrives": {"true"}, "includeItemsFromAllDrives": {"true"},
		}
		if token != "" {
			params.Set("pageToken", token)
		}
		var page listResponse
		if err := c.get(ctx, "/files", params, &page); err != nil {
			return nil, err
		}
		all = append(all, page.Files...)
		if page.NextPageToken == "" {
			return all, nil
		}
		token = page.NextPageToken
	}
}

// Scan returns folders plus supported book/archive files and fonts.
// File size is not capped: scanning only reads Drive listing metadata, not file contents.
func (c *Client) Scan(ctx context.Context, rootID string) ([]File, error) {
	if _, err := c.GetFolder(ctx, rootID); err != nil {
		return nil, err
	}
	var out []File
	var walk func(string) error
	walk = func(parent string) error {
		children, err := c.ListChildren(ctx, parent)
		if err != nil {
			return err
		}
		for _, f := range children {
			f.ParentID = parent
			if f.MIMEType == folderMIME {
				out = append(out, f)
				if err := walk(f.ID); err != nil {
					return err
				}
				continue
			}
			if isSupportedBook(f) {
				out = append(out, f)
			}
		}
		return nil
	}
	if err := walk(rootID); err != nil {
		return nil, err
	}
	return out, nil
}

func isSupportedBook(f File) bool {
	if f.Size < 0 {
		return false
	}
	switch strings.ToLower(filepath.Ext(f.Name)) {
	case ".epub", ".mobi", ".azw3", ".cbz", ".lit", ".chm", ".prc", ".pdf", ".zip", ".rar", ".doc", ".docx", ".txt", ".md", ".cpfont", ".ttf", ".otf":
		return true
	default:
		return false
	}
}

func IsSupportedBook(f File) bool { return isSupportedBook(f) }

func (c *Client) Open(ctx context.Context, fileID, rangeHeader string) (*http.Response, error) {
	params := url.Values{"alt": {"media"}}
	params.Set("key", c.apiKey)
	u := apiBase + "/files/" + url.PathEscape(fileID) + "?" + params.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "*/*")
	if rangeHeader != "" {
		req.Header.Set("Range", rangeHeader)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		resp.Body.Close()
		return nil, fmt.Errorf("Google Drive download returned %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	return resp, nil
}

// FindPublicFileByName resolves a public Drive snapshot manifest by exact name.
func (c *Client) FindPublicFileByName(ctx context.Context, name string) (string, error) {
	q := "name = '" + escapeQuery(name) + "' and trashed = false"
	params := url.Values{
		"q":        {q},
		"pageSize": {"10"},
		"fields":   {"files(id,name,mimeType,modifiedTime,parents)"},
		"orderBy":  {"modifiedTime desc"},
	}

	var result struct {
		Files []struct {
			ID           string   `json:"id"`
			Name         string   `json:"name"`
			MIMEType     string   `json:"mimeType"`
			ModifiedTime string   `json:"modifiedTime"`
			Parents      []string `json:"parents"`
		} `json:"files"`
	}

	if err := c.get(ctx, "/files", params, &result); err != nil {
		return "", err
	}

	log.Printf("SNAPSHOT manifest lookup: name=%q candidates=%d", name, len(result.Files))

	for i, f := range result.Files {
		log.Printf(
			"SNAPSHOT manifest candidate[%d]: id=%s name=%q mimeType=%s modifiedTime=%s parents=%v",
			i, f.ID, f.Name, f.MIMEType, f.ModifiedTime, f.Parents,
		)
	}

	if len(result.Files) == 0 {
		log.Printf("SNAPSHOT manifest not found: name=%q", name)
		return "", nil
	}

	// Results are ordered by modifiedTime descending; prefer the newest if an
	// interrupted Apps Script run left a duplicate manifest behind.
	selected := result.Files[0]
	log.Printf("SNAPSHOT manifest selected: id=%s name=%q parents=%v",
		selected.ID, selected.Name, selected.Parents)

	return selected.ID, nil
}
	// Results are ordered by modifiedTime descending; prefer the newest if an
	// interrupted Apps Script run left a duplicate manifest behind.
	return result.Files[0].ID, nil
}

// DownloadJSON reads a public Drive JSON file by ID using the configured API key.
func (c *Client) DownloadJSON(ctx context.Context, fileID string, dst any) error {
	resp, err := c.Open(ctx, fileID, "")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	dec := json.NewDecoder(io.LimitReader(resp.Body, 64*1024*1024))
	return dec.Decode(dst)
}

func escapeQuery(s string) string { return strings.ReplaceAll(s, "'", "\\'") }
func IsFolder(f File) bool        { return f.MIMEType == folderMIME }
