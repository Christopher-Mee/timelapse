from PIL import Image, ImageDraw, ImageFont # pip install Pillow
import ctypes
import numpy as np

# helvetica0 = "C:/Users/goodf/Desktop/Helvetica.ttf"
# helvetica1 = "C:/Users/goodf/Desktop/HelveticaNeueLTStd-Roman.otf"
# helvetica2 = "C:/Users/goodf/Desktop/New Font/Helvetica.ttf"
helvetica = "C:/Users/goodf/Desktop/New Font/Helvetica___.ttf"
# helvetica2 = "C:/Users/goodf/Desktop/helvetica.ttf"

helveticaBold0 = "C:/Users/goodf/Desktop/Helvetica-Bold.ttf"
helveticaBold1 = "C:/Users/goodf/Desktop/HelveticaNeueLTStd-Bd.otf"
helveticaBold = "C:/Users/goodf/Desktop/New Font/HelveticaBd.ttf"
helveticaBold3 = "C:/Users/goodf/Desktop/New Font/HelveticaBd___.ttf"

def getTextDimensions1(text, font_size, font_path):
    # Load font
    font = ImageFont.truetype(font_path, font_size)
    
    # Create a temporary image and draw object
    img = Image.new('RGB', (1, 1), color = (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Get bounding box of text
    bbox = draw.textbbox((0, 0), text, font=font)
    
    # Calculate width and height
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    
    return (width, height)

def getTextDimensions2(text, points, font_path):
    font = ImageFont.truetype(font_path, points)
    bbox = font.getbbox(text)
    width = bbox[2] - bbox[0]
    height = bbox[3]
    return (width, height)

def getTextDimensions3(text, points, font_path):
    class SIZE(ctypes.Structure):
        _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

    hdc = ctypes.windll.user32.GetDC(0)
    hfont = ctypes.windll.gdi32.CreateFontA(points, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, font_path)
    hfont_old = ctypes.windll.gdi32.SelectObject(hdc, hfont)

    size = SIZE(0, 0)
    ctypes.windll.gdi32.GetTextExtentPoint32A(hdc, text, len(text), ctypes.byref(size))

    ctypes.windll.gdi32.SelectObject(hdc, hfont_old)
    ctypes.windll.gdi32.DeleteObject(hfont)

    width = size.cx
    height = size.cy

    return (width, height)

def getTextDimensions4(text, points, font_path):
    
    image = Image.new("RGB", (200, 80))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, points)
    
    draw.text((20, 20), text, font=font)
    bbox = draw.textbbox((20, 20), text, font=font)
    
    width = bbox[2] - bbox[0]
    height = bbox[3]
    
    return (width, height)

def getTextDimensions5(text, points, font_path):
    global imgID
    
    X1 = 0
    X2 = 2
    
    im = Image.new('RGB', (400, 100), (200, 200, 200))
    font = ImageFont.truetype(font_path, size=points)
    ascent, descent = font.getmetrics()
    (width, height), (offset_x, offset_y) = font.font.getsize(text)
    bbox = font.getmask(text).getbbox()
#     leftKerningWidth = bbox[X1]
#     rightKerningWidth = width - bbox[X2]
    
    draw = ImageDraw.Draw(im)
    draw.rectangle([(0, 0), (width - 1, offset_y)], fill=(237, 127, 130))  # Red
    draw.rectangle([(0, offset_y), (width - 1, ascent)], fill=(202, 229, 134))  # Green
    draw.rectangle([(0, ascent), (width - 1, ascent + descent - 1)], fill=(134, 190, 229))  # Blue
    draw.rectangle(font.getmask(text).getbbox(), outline=(0, 0, 0))  # Black
    draw.text((0, 0), text, font=font, fill=(0, 0, 0))
    im.save('result' + str(imgID) + '.png')
    imgID += 1
    
    print(text)
#     print(width, height)
#     print(offset_x, offset_y)
#     print('Red height', offset_y)
#     print('Green height', ascent - offset_y)
#     print('Blue height', descent) 
#     print('Black', bbox)
#     print('Left kerning', leftKerningWidth)
#     print('Right kerning', rightKerningWidth)
#     print('========================================')
    
    height = ascent
    
    return (width, height)

def getTextDimensions6(text, points, font_file):
    global imgID
    im = Image.new('RGB', (400, 300), (200, 200, 200))
    font = ImageFont.truetype(font_file, size=points)
    ascent, descent = font.getmetrics()
    (width, height), (offset_x, offset_y) = font.font.getsize(text)
    
    draw = ImageDraw.Draw(im)
    draw.rectangle([(0, offset_y), (font.getmask(text).getbbox()[2], ascent + descent)], fill=(202, 229, 134))
    draw.text((0, 0), text, font=font, fill=(0, 0, 0))
    im.save('result' + str(imgID) + '.png')
#     print('Font pixel', (ascent + descent - offset_y) * (font.getmask(text).getbbox()[2]))
    imgID += 1
    
    return (width, height)

def getTextDimensions7(text, points, font_file):
    font = ImageFont.truetype(font_file, size=points)
    ascent, descent = font.getmetrics()

    text_width = font.getmask(text).getbbox()[2]
    text_height = font.getmask(text).getbbox()[3] + descent

    return (text_width, text_height)

def average(lst): 
    return sum(lst) / len(lst)

def results(measurementMethod, point, font, selectedRange):
    resultsX = []
    resultsY = []
    
    for char in selectedRange:
        text = chr(char)
        result = measurementMethod(text, point, font)
        #print(str(char) + " (" + text + ") : " + str(result))
        resultsX.append(result[0])
        resultsY.append(result[1])

    print("W:" + str(max(resultsX)) + " , " + str(np.round(average(resultsX), decimals=2)))
    print("H:" + str(max(resultsY)) + " , " + str(np.round(average(resultsY), decimals=2)))
    
if __name__ == "__main__":
    global imgID # used to draw bbox and ascent/descent boxes
    imgID = 0
    
    methods = [
#         getTextDimensions1,
#         getTextDimensions2,
#         getTextDimensions3,
#         getTextDimensions4,
        getTextDimensions5,
#         getTextDimensions6,
#         getTextDimensions7
        ]
    
    # Ascii table ranges
    numbers = list(range(48, (57 + 1)))
    time = numbers + [58]
    ampm = [65, 77, 80]
    upperCase = list(range(65, (90 + 1)))
    lowerCase = list(range((65 + 32), (90 + 32 + 1)))
    comma = [44]
    date = upperCase + comma + numbers
    
    
#     print(getTextDimensions5("Hello, world", 72, helvetica))
#     print(getTextDimensions5("hello, world", 72, helvetica))
#     for method in methods:
#          print(method.__name__)
#         results(method, 36, helveticaBold, ampm) 			# time string
#         results(method, 72, helvetica, time) 			# time string
#          results(method, 36, helveticaBold, date) 	# Date and ampm strings
#         print()

#     print(getTextDimensions5("AM", 36, helveticaBold))
#     print(getTextDimensions5("PM", 36, helveticaBold))

    days = [
        'MON',
        'TUE',
        'WED',
        'THU',
        'FRI',
        'SAT',
        'SUN',
        ]

    date = "    FEB 09, 2017"
    dateTab = "\t" + "FEB 09, 2017"
    for day in days:
        getTextDimensions5(day + date, 36, helveticaBold)
    
#     time = '11:33'
#     print(getTextDimensions5(time, 72, helvetica0))
#     print(getTextDimensions5(time, 72, helvetica1))
#     print(getTextDimensions5(time, 72, helvetica2))
#     print(getTextDimensions5(time, 72, helvetica3))
#     print(getTextDimensions5(date, 36, helveticaBold))
    
#     for i in range(1, 10):
#         print(getTextDimensions5(str(i), 72, helvetica))

#     print(getTextDimensions5(' ', 72, helvetica))

#     getTextDimensions5('11 : 59 AM', 69, helvetica)
#     getTextDimensions5('12 : 00 PM', 69, helvetica) 
#     getTextDimensions5('11 : 59 AM', 69, helvetica1)
#     getTextDimensions5('12 : 00 PM', 69, helvetica1)
#     getTextDimensions5('11 : 59 AM', 69, helvetica2)
#     getTextDimensions5('12 : 00 PM', 69, helvetica2)

#     start = 7
#     end = start
#     for i in range(start, end + 1):
#         for j in range(50,59 + 1):
#             timeStr = (
#                 (str(i) if i <= 9 else str(i)) # '0' +  
#                 + ':' 
#                 + ('0' + str(j) if j <= 9 else str(j)) 
#                 + ' AM'
#             )
#             
#             getTextDimensions5(timeStr, 72, helvetica)
    