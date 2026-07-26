pub struct TextChunker {
    chunk_size: usize,
    overlap: usize,
}

impl TextChunker {
    pub fn new(chunk_size: usize, overlap: usize) -> Self {
        Self { chunk_size, overlap }
    }
    
    pub fn default() -> Self {
        Self {
            chunk_size: 600,
            overlap: 100,
        }
    }
    
    pub fn chunk(&self, text: &str) -> Vec<String> {
        if text.len() <= self.chunk_size {
            return vec![text.to_string()];
        }
        
        let mut chunks = Vec::new();
        let mut start = 0;
        let step = self.chunk_size - self.overlap;
        
        while start < text.len() {
            let end = (start + self.chunk_size).min(text.len());
            let chunk = &text[start..end];
            
            if !chunk.trim().is_empty() {
                chunks.push(chunk.to_string());
            }
            
            if end >= text.len() {
                break;
            }
            
            start += step;
        }
        
        chunks
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_chunking_short_text() {
        let chunker = TextChunker::new(100, 20);
        let text = "Short text";
        let chunks = chunker.chunk(text);
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0], "Short text");
    }
    
    #[test]
    fn test_chunking_with_overlap() {
        let chunker = TextChunker::new(10, 3);
        let text = "0123456789ABCDEFGHIJ";
        let chunks = chunker.chunk(text);
        
        assert!(chunks.len() > 1);
        assert_eq!(chunks[0].len(), 10);
    }
}
