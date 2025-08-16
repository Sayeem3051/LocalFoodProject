# 🍽️ Local Food Wastage Management System

A comprehensive web application built with Streamlit to connect food providers with those in need, helping reduce food waste and support the community.

## ✨ Features

- **Browse Food Listings**: View and filter available food items by location, provider, food type, and meal type
- **Admin Management**: 
  - Manage food providers and their information
  - Manage food listings (add, edit, delete)
  - Manage food receivers
- **Analytics Dashboard**: View system statistics and insights
- **Activity History**: Track all system changes and activities for audit purposes
- **Food Claims**: Submit and manage food claims
- **Provider Portal**: Allow providers to manage their own listings

## 🎯 Purpose

This platform aims to:
- Reduce food waste by connecting providers with receivers
- Support community members in need
- Provide transparency and tracking of food donations
- Create a sustainable food distribution system

## 🛠️ Technology Stack

- **Frontend**: Streamlit (Python web framework)
- **Backend**: Python
- **Database**: SQLite
- **Styling**: Custom CSS with dark theme and animations

## 🚀 Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sayeem3051/LocalFoodProject.git
   cd LocalFoodProject
   ```

2. **Install dependencies**
   ```bash
   pip install streamlit pandas sqlite3
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Access the app**
   - Local URL: http://localhost:8501
   - Network URL: http://[your-ip]:8501

## 📱 Usage

1. **Browse Listings**: View available food items and submit claims
2. **Admin Functions**: Manage providers, listings, and receivers
3. **Analytics**: Monitor system performance and food distribution
4. **Activity Tracking**: View audit trail of all system activities

## 🎨 UI Features

- **Dark Theme**: Modern, eye-friendly dark interface
- **Animations**: Smooth transitions and hover effects
- **Responsive Design**: Works on desktop and mobile devices
- **Interactive Elements**: Hover effects, smooth transitions, and visual feedback

## 📊 Database Schema

The system uses the following main tables:
- `food_listings`: Food items available for donation
- `providers`: Food providers/organizations
- `receivers`: Food recipients
- `claims`: Food claim requests

## 🔒 Security Features

- Input validation and sanitization
- Activity logging for audit trails
- Session management
- Database connection security

## 👨‍💻 Developer

**Created by:** Abkari mohammed Sayeem

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support or questions, please open an issue on GitHub or contact the developer.

---

**Made with ❤️ for the community**
