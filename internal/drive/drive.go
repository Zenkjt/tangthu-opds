package drive

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

const (
	apiBase    = "https://www.googleapis.com/drive/v3"
	folderMIME = "application/vnd.google-apps.folder"
)

type File struct {
	ID           string `json:"id"`
	ParentID     string `json:"-"`
	Name         string `json:"name"`
	MIMEType     string `json:"mimeType"`
	Size         int64  `json:"size,string"`
	ModifiedTime string `json:"modifiedTime"`
	MD5Checksum  string `json:"md5Checksum"`
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

func (c *Client) get(ctx context.Context, endpoint string, params url.Values, dst any) error {
	params.Set("key", c.apiKey)
	u := apiBase + endpoint + "?" + params.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("Google Drive API returned %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	return json.NewDecoder(resp.Body).Decode(dst)
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
			"fields":            {"nextPageToken,files(id,name,mimeType,size,modifiedTime,md5Checksum)"},
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
			out = append(out, f)
			if f.MIMEType == folderMIME {
				if err := walk(f.ID); err != nil {
					return err
				}
			}
		}
		return nil
	}
	if err := walk(rootID); err != nil {
		return nil, err
	}
	return out, nil
}

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

func escapeQuery(s string) string { return strings.ReplaceAll(s, "'", "\\'") }
func IsFolder(f File) bool        { return f.MIMEType == folderMIME }
