def find_and_replace_hex(input_hex, output_hex, input_file_path, output_file_path):
    # Convert input and output hex strings to bytes
    input_bytes = bytes.fromhex(input_hex)
    output_bytes = bytes.fromhex(output_hex)

    # Read the input binary file
    with open(input_file_path, 'rb') as input_file:
        file_data = input_file.read()

    # Find the index of the input_bytes in the file_data
    try:
        index = file_data.index(input_bytes)
    except ValueError:
        print("找不到字串")
        return


    # Replace the bytes in the file_data with the output_bytes
    file_data = file_data[:index] + output_bytes + file_data[index+len(input_bytes):]

    # Write the modified data to the output binary file
    with open(output_file_path, 'wb') as output_file:
        output_file.write(file_data)

    print("成功")

if __name__ == "__main__":
    input_hex  = "B1A3B4E6B5C4CAFDBEDD2020202020"
    output_hex = "E4BF9DE5AD98E79A84E695B0E68DAE"
    input_file_path = "usdtwndsub._bp"
    output_file_path = "usdtwndsub._bp"

    #input_hex必須=output_hex長度，不夠補hex

    find_and_replace_hex(input_hex, output_hex, input_file_path, output_file_path)
