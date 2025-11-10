"""
Instagram contact button harvester
Extracts business email/contact info from profiles
"""
from typing import List, Dict, Optional
import instaloader
from loguru import logger
import re
from .base_scraper import BaseScraper


class InstagramScraper(BaseScraper):
    """Scrape Instagram business profiles for contact info"""
    
    def __init__(self, session_file: Optional[str] = None):
        super().__init__("instagram_scraper")
        
        # Initialize Instaloader
        self.L = instaloader.Instaloader()
        
        # Load session if provided
        if session_file:
            try:
                self.L.load_session_from_file(session_file)
                logger.info(f"[{self.name}] Loaded Instagram session")
            except Exception as e:
                logger.warning(f"[{self.name}] Could not load session: {str(e)}")
    
    def scrape(self, hashtag: str = "hiphop", max_posts: int = 100) -> List[Dict]:
        """
        Scrape profiles from hashtag posts
        """
        logger.info(f"[{self.name}] Scraping hashtag: #{hashtag}")
        
        try:
            posts = self.L.get_hashtag_posts(hashtag)
            
            seen_profiles = set()
            
            for i, post in enumerate(posts):
                if i >= max_posts:
                    break
                
                try:
                    owner_username = post.owner_username
                    
                    if owner_username not in seen_profiles:
                        seen_profiles.add(owner_username)
                        
                        profile_data = self.scrape_profile(owner_username)
                        if profile_data:
                            self.save_result(profile_data)
                            logger.info(f"[{self.name}] Scraped profile: @{owner_username}")
                
                except Exception as e:
                    logger.error(f"[{self.name}] Error processing post: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"[{self.name}] Hashtag scraping failed: {str(e)}")
        
        return self.get_results()
    
    def scrape_profile(self, username: str) -> Optional[Dict]:
        """
        Scrape a specific Instagram profile
        """
        try:
            profile = instaloader.Profile.from_username(self.L.context, username)
            
            # Extract contact info from bio
            bio = profile.biography or ""
            emails = self.extract_emails(bio)
            
            # Extract URLs from bio
            external_url = profile.external_url or ""
            
            # Check if business account
            is_business = profile.is_business_account
            
            profile_data = {
                "username": username,
                "full_name": profile.full_name,
                "bio": bio,
                "follower_count": profile.followers,
                "following_count": profile.followees,
                "post_count": profile.mediacount,
                "is_business_account": is_business,
                "is_verified": profile.is_verified,
                "external_url": external_url,
                "emails": emails,
                "profile_url": f"https://www.instagram.com/{username}/",
                "profile_pic_url": profile.profile_pic_url,
            }
            
            # Extract business contact info if available
            if is_business:
                profile_data["business_category"] = getattr(profile, 'business_category_name', None)
                
                # Try to get business contact info (requires login)
                try:
                    business_email = getattr(profile, 'business_email', None)
                    if business_email:
                        profile_data["business_email"] = business_email
                        if business_email not in emails:
                            emails.append(business_email)
                except:
                    pass
            
            return profile_data
        
        except Exception as e:
            logger.error(f"[{self.name}] Error scraping profile @{username}: {str(e)}")
            return None
    
    def scrape_followers(self, username: str, max_followers: int = 100) -> List[Dict]:
        """
        Scrape followers of a profile (useful for finding similar curators)
        """
        logger.info(f"[{self.name}] Scraping followers of @{username}")
        results = []
        
        try:
            profile = instaloader.Profile.from_username(self.L.context, username)
            followers = profile.get_followers()
            
            for i, follower in enumerate(followers):
                if i >= max_followers:
                    break
                
                try:
                    follower_data = self.scrape_profile(follower.username)
                    if follower_data:
                        results.append(follower_data)
                except Exception as e:
                    continue
        
        except Exception as e:
            logger.error(f"[{self.name}] Error scraping followers: {str(e)}")
        
        return results
    
    def find_music_curators(self, keywords: List[str] = None) -> List[Dict]:
        """
        Find music curator profiles based on bio keywords
        """
        if keywords is None:
            keywords = ["playlist", "curator", "music", "hip hop", "rap", "a&r", "dj"]
        
        results = []
        
        # Search by hashtags
        hashtags = ["playlistcurator", "musiccurator", "hiphop", "newmusic"]
        
        for hashtag in hashtags:
            try:
                posts = self.L.get_hashtag_posts(hashtag)
                
                seen = set()
                for i, post in enumerate(posts):
                    if i >= 50:
                        break
                    
                    username = post.owner_username
                    if username in seen:
                        continue
                    
                    seen.add(username)
                    
                    try:
                        profile_data = self.scrape_profile(username)
                        
                        if profile_data:
                            bio_lower = profile_data.get('bio', '').lower()
                            
                            # Check if bio contains relevant keywords
                            if any(keyword.lower() in bio_lower for keyword in keywords):
                                results.append(profile_data)
                                logger.info(f"[{self.name}] Found curator: @{username}")
                    
                    except Exception as e:
                        continue
            
            except Exception as e:
                logger.error(f"[{self.name}] Error searching #{hashtag}: {str(e)}")
                continue
        
        return results
    
    def extract_contact_from_bio(self, bio: str) -> Dict[str, any]:
        """
        Extract all contact information from bio
        """
        contact_info = {
            "emails": [],
            "phone_numbers": [],
            "booking_keywords": []
        }
        
        # Extract emails
        contact_info["emails"] = self.extract_emails(bio)
        
        # Extract phone numbers
        phone_pattern = r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, bio)
        contact_info["phone_numbers"] = phones
        
        # Look for booking keywords
        booking_keywords = ["booking", "bookings", "press", "management", "contact", "dm for"]
        found_keywords = [kw for kw in booking_keywords if kw.lower() in bio.lower()]
        contact_info["booking_keywords"] = found_keywords
        
        return contact_info
